"""Entry point — thin wrapper around the pnl package factory."""
from pnl import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
