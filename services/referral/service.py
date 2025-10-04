import logging
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from api.models import User, Purchase, ReferralLink, PartnerCommissionLedger, CoinBonusLedger, PartnerBalance
from api.models.user import UserRole, ReferrerType
from api.routers.payments.schemas import PaymentObject


class ReferralService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def handle_successful_payment(self, payment_object: PaymentObject):
        """
        Главный обработчик успешного платежа.
        Определяет пользователя, его реферера и запускает соответствующую логику начислений.
        """
        # В метаданных платежа должен быть chat_id пользователя
        chat_id = payment_object.metadata.get("chat_id")
        if not chat_id:
            logging.warning(f"No chat_id in payment metadata for payment {payment_object.id}")
            return

        # 1. Найти пользователя по chat_id
        user = await self._get_user_by_chat_id(chat_id)
        if not user:
            logging.error(f"User with chat_id {chat_id} not found for payment {payment_object.id}")
            return

        # 2. Проверить, есть ли у пользователя реферер
        if not user.referrer_id:
            logging.info(f"User {user.id} has no referrer. No referral action needed.")
            return

        # 3. Создать и сохранить запись о покупке
        purchase = await self._create_purchase_record(user, payment_object)

        # 4. Определить тип реферера и применить логику
        if user.referrer_type == ReferrerType.USER:
            # Схема "user -> user"
            if purchase.is_first_for_user:
                await self._grant_user_to_user_bonus(user, purchase)
        elif user.referrer_type == ReferrerType.PARTNER:
            # Схема "partner -> user"
            await self._grant_partner_commission(user, purchase)

        await self.session.commit()

    async def _get_user_by_chat_id(self, chat_id: str) -> User | None:
        result = await self.session.execute(select(User).where(User.chat_id == chat_id))
        return result.scalar_one_or_none()

    async def _create_purchase_record(self, user: User, payment: PaymentObject) -> Purchase:
        """
        Создает запись о покупке в БД.
        """
        # Проверяем, первая ли это покупка для пользователя
        existing_purchases = await self.session.execute(
            select(Purchase).where(Purchase.user_id == user.id)
        )
        is_first = not existing_purchases.first()

        purchase = Purchase(
            id=UUID(payment.id), # Используем ID платежа как ID покупки для идемпотентности
            user_id=user.id,
            amount_minor=int(float(payment.amount.value) * 100),
            currency=payment.amount.currency,
            is_first_for_user=is_first,
            created_at=payment.captured_at
        )
        self.session.add(purchase)
        await self.session.flush()
        return purchase

    async def _grant_user_to_user_bonus(self, buyer: User, purchase: Purchase):
        """
        Начисляет по 1 coin покупателю и его рефереру-пользователю.
        """
        referrer_id = buyer.referrer_id
        referrer = await self.session.get(User, referrer_id)

        if not referrer:
            logging.error(f"Referrer user with id {referrer_id} not found.")
            return

        # Начисляем бонус покупателю
        buyer.coins += 1
        self.session.add(buyer)
        buyer_bonus = CoinBonusLedger(
            giver_id=referrer.id,
            receiver_id=buyer.id,
            purchase_id=purchase.id,
            coins=1,
            status="accrued"
        )
        self.session.add(buyer_bonus)

        # Начисляем бонус рефереру
        referrer.coins += 1
        self.session.add(referrer)
        referrer_bonus = CoinBonusLedger(
            giver_id=referrer.id, # Технически, "даритель" бонуса - это система по правилу
            receiver_id=referrer.id,
            purchase_id=purchase.id,
            coins=1,
            status="accrued"
        )
        self.session.add(referrer_bonus)

        logging.info(f"Granted 1 coin bonus to user {buyer.id} and referrer {referrer.id} for purchase {purchase.id}")


    async def _grant_partner_commission(self, buyer: User, purchase: Purchase):
        """
        Начисляет комиссию партнеру-рефереру.
        """
        partner_id = buyer.referrer_id
        ref_link_id = buyer.ref_link_id

        ref_link = await self.session.get(ReferralLink, ref_link_id)
        if not ref_link or not ref_link.percent:
            logging.error(f"Referral link {ref_link_id} not found or has no percent set.")
            return

        # Расчет комиссии
        commission_amount = int(purchase.amount_minor * (ref_link.percent / 100))

        # Запись в леджер комиссий
        commission_entry = PartnerCommissionLedger(
            partner_id=partner_id,
            user_id=buyer.id,
            purchase_id=purchase.id,
            ref_link_id=ref_link_id,
            base_amount_minor=purchase.amount_minor,
            percent=ref_link.percent,
            commission_minor=commission_amount,
            status="accrued"
        )
        self.session.add(commission_entry)

        # Обновление баланса партнера
        partner_balance = await self.session.get(PartnerBalance, partner_id)
        if not partner_balance:
            partner_balance = PartnerBalance(partner_id=partner_id, balance_minor=0, hold_minor=0)
            self.session.add(partner_balance)

        partner_balance.balance_minor += commission_amount

        logging.info(f"Granted {commission_amount} commission to partner {partner_id} for purchase {purchase.id}")

    async def handle_refund(self, payment_object: PaymentObject):
        """
        Обрабатывает возврат платежа, сторнируя начисленные бонусы или комиссии.
        """
        purchase = await self.session.get(Purchase, UUID(payment_object.id))
        if not purchase:
            logging.warning(f"Purchase with id {payment_object.id} not found for refund.")
            return

        # 1. Сторнирование комиссии партнера
        commission_ledger_entry = await self.session.scalar(
            select(PartnerCommissionLedger).where(PartnerCommissionLedger.purchase_id == purchase.id)
        )
        if commission_ledger_entry:
            partner_balance = await self.session.get(PartnerBalance, commission_ledger_entry.partner_id)
            if partner_balance:
                partner_balance.balance_minor -= commission_ledger_entry.commission_minor
                self.session.add(partner_balance)

            # Создаем сторнирующую запись
            storno_entry = PartnerCommissionLedger(
                partner_id=commission_ledger_entry.partner_id,
                user_id=commission_ledger_entry.user_id,
                purchase_id=purchase.id,
                ref_link_id=commission_ledger_entry.ref_link_id,
                base_amount_minor=-commission_ledger_entry.base_amount_minor,
                percent=commission_ledger_entry.percent,
                commission_minor=-commission_ledger_entry.commission_minor,
                status="reversed",
                reason=f"Refund for payment {payment_object.id}"
            )
            self.session.add(storno_entry)
            logging.info(f"Reversed commission for partner {commission_ledger_entry.partner_id} for purchase {purchase.id}")

        # 2. Сторнирование бонусов user-to-user (если применимо)
        if purchase.is_first_for_user:
            # Находим оригинального реферера (giver) и покупателя (receiver)
            original_giver_id_query = await self.session.execute(
                select(User.referrer_id).where(User.id == purchase.user_id)
            )
            original_giver_id = original_giver_id_query.scalar_one_or_none()
            buyer_id = purchase.user_id

            if original_giver_id and buyer_id:
                # Списываем монету у реферера
                giver = await self.session.get(User, original_giver_id)
                if giver:
                    giver.coins -= 1
                    self.session.add(giver)
                    # Логируем сторно
                    storno_giver = CoinBonusLedger(giver_id=original_giver_id, receiver_id=original_giver_id, purchase_id=purchase.id, coins=-1, status="reversed")
                    self.session.add(storno_giver)
                    logging.info(f"Reversed 1 coin from referrer {original_giver_id} for purchase {purchase.id}")

                # Списываем монету у покупателя
                buyer = await self.session.get(User, buyer_id)
                if buyer:
                    buyer.coins -= 1
                    self.session.add(buyer)
                    # Логируем сторно
                    storno_buyer = CoinBonusLedger(giver_id=original_giver_id, receiver_id=buyer_id, purchase_id=purchase.id, coins=-1, status="reversed")
                    self.session.add(storno_buyer)
                    logging.info(f"Reversed 1 coin from buyer {buyer_id} for purchase {purchase.id}")

        await self.session.commit()