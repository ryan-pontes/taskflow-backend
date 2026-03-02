from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client
from app.config import settings
from app.models.schemas import UserCreate, User, OrgCreate
from app.integrations.supabase import (
    supabase_admin, 
    create_organization, 
    create_member,
    get_member_by_user_id
)

router = APIRouter()
security = HTTPBearer()

# === Dependency: Get Current User ===
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Validar token e retornar usuário"""
    try:
        # Verificar token com Supabase
        user_response = supabase_admin.auth.get_user(credentials.credentials)
        user = user_response.user
        
        if not user:
            raise HTTPException(status_code=401, detail="Token inválido")
        
        # Buscar dados do member
        member = await get_member_by_user_id(user.id)
        
        return {
            "id": user.id,
            "email": user.email,
            "name": user.user_metadata.get("name", ""),
            "org_id": member.get("org_id") if member else None,
            "role": member.get("role", "member") if member else "manager",
            "member_id": member.get("id") if member else None
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Não autorizado: {str(e)}")


# === Endpoints ===
@router.post("/signup")
async def signup(data: UserCreate, org_name: str = None):
    """Criar conta de gestor (com organização)"""
    try:
        # Criar usuário no Supabase Auth
        auth_response = supabase_admin.auth.admin.create_user({
            "email": data.email,
            "password": data.password,
            "user_metadata": {"name": data.name},
            "email_confirm": True
        })
        
        user = auth_response.user
        
        # Criar organização
        org = await create_organization(
            name=org_name or f"Org de {data.name}",
            owner_id=user.id
        )
        
        # Criar member como manager
        member = await create_member(
            user_id=user.id,
            org_id=org["id"],
            role="manager",
            profile={"name": data.name}
        )
        
        return {
            "user_id": user.id,
            "org_id": org["id"],
            "member_id": member["id"],
            "message": "Conta criada com sucesso"
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
async def login(email: str, password: str):
    """Login e retornar token"""
    try:
        response = supabase_admin.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "user": {
                "id": response.user.id,
                "email": response.user.email,
                "name": response.user.user_metadata.get("name", "")
            }
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Retornar dados do usuário logado"""
    return user


@router.post("/refresh")
async def refresh_token(refresh_token: str):
    """Renovar access token"""
    try:
        response = supabase_admin.auth.refresh_session(refresh_token)
        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail="Token inválido")
