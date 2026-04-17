"""Cliente Supabase — instancia única compartida por toda la app.

Se importa así en cualquier fichero:
    from auth.supabase_client import supabase

Luego puedes llamar, por ejemplo:
    response = supabase.auth.sign_in_with_password({"email": ..., "password": ...})
"""
from supabase import create_client, Client

from utils.config import SUPABASE_URL, SUPABASE_ANON_KEY

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError(
        "SUPABASE_URL o SUPABASE_ANON_KEY no están configuradas. "
        "Copia .env.example a .env y rellena tus credenciales de Supabase."
    )

# Creamos el cliente una sola vez al importar el módulo
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
