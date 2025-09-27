# Needed package-manger `UV astral`:
 - Linux:
    ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
 - Windows:
    ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

# Install Packages:
```bash
uv sync
```

# Installing additional packages:
```bash
uv add <package-name>
```
# Alembic | Migrations
 - Create migrations:
   ```bash
   uv run alembic revision
   ```


