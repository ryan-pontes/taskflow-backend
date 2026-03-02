import json
from datetime import datetime, timedelta
from typing import List, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from app.config import settings

class GoogleCalendarClient:
    def __init__(self, credentials_data: dict, user_id: str = None):
        self.credentials_data = credentials_data
        self.user_id = user_id

    def _get_credentials(self) -> Credentials:
        import asyncio
        from google.auth.transport.requests import Request

        creds = Credentials(
            token=self.credentials_data.get("access_token"),
            refresh_token=self.credentials_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
        )

        expires_at_str = self.credentials_data.get("expires_at")
        if expires_at_str:
            from datetime import datetime, timezone
            expires_at = datetime.fromisoformat(expires_at_str)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(timezone.utc):
                creds.refresh(Request())
                # Persistir tokens atualizados
                if self.user_id:
                    new_expiry = creds.expiry.replace(tzinfo=timezone.utc).isoformat() if creds.expiry else None
                    new_creds = {
                        "access_token": creds.token,
                        "refresh_token": creds.refresh_token or self.credentials_data.get("refresh_token"),
                        "expires_at": new_expiry,
                    }
                    self.credentials_data = new_creds
                    try:
                        loop = asyncio.get_event_loop()
                        loop.create_task(self._persist_credentials(new_creds))
                    except RuntimeError:
                        pass

        return creds

    async def _persist_credentials(self, new_creds: dict):
        from app.integrations.token_store import update_google_credentials
        await update_google_credentials(self.user_id, new_creds)

    def _get_service(self):
        """Criar serviço com credentials do usuário"""
        credentials = self._get_credentials()
        return build('calendar', 'v3', credentials=credentials)
    
    async def get_events(
        self,
        time_min: datetime = None,
        time_max: datetime = None,
        max_results: int = 50
    ) -> List[dict]:
        """Buscar eventos do calendário"""
        service = self._get_service()
        
        if not time_min:
            time_min = datetime.utcnow()
        if not time_max:
            time_max = time_min + timedelta(days=7)
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min.isoformat() + 'Z',
            timeMax=time_max.isoformat() + 'Z',
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        return events_result.get('items', [])
    
    async def get_availability(
        self,
        date: datetime = None
    ) -> dict:
        """Verificar disponibilidade em uma data"""
        if not date:
            date = datetime.utcnow()

        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        events = await self.get_events(start_of_day, end_of_day)
        
        # Calcular horas ocupadas vs livres
        busy_hours = 0
        for event in events:
            start = event.get('start', {}).get('dateTime')
            end = event.get('end', {}).get('dateTime')
            if start and end:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                busy_hours += (end_dt - start_dt).total_seconds() / 3600
        
        work_hours = 8  # Assumindo dia de 8h
        free_hours = max(0, work_hours - busy_hours)
        
        return {
            "date": date.isoformat(),
            "events_count": len(events),
            "busy_hours": round(busy_hours, 1),
            "free_hours": round(free_hours, 1),
            "availability_percentage": round((free_hours / work_hours) * 100)
        }
    
    async def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        description: str = None,
        attendees: List[str] = None
    ) -> dict:
        """Criar evento no calendário"""
        service = self._get_service()
        
        event = {
            'summary': summary,
            'start': {
                'dateTime': start.isoformat(),
                'timeZone': 'America/Sao_Paulo',
            },
            'end': {
                'dateTime': end.isoformat(),
                'timeZone': 'America/Sao_Paulo',
            }
        }
        
        if description:
            event['description'] = description
        
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]
        
        result = service.events().insert(
            calendarId='primary',
            body=event,
            sendUpdates='all' if attendees else 'none'
        ).execute()
        
        return result
    
    async def create_focus_block(
        self,
        date: datetime,
        start_hour: int,
        duration_hours: int,
        title: str = "Bloco de Foco"
    ) -> dict:
        """Criar bloco de foco no calendário"""
        start = date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=duration_hours)

        return await self.create_event(
            summary=title,
            start=start,
            end=end,
            description="Bloco de foco criado pelo TaskFlow Manager"
        )


async def get_google_client(user_id: str) -> Optional["GoogleCalendarClient"]:
    """Retorna cliente Google Calendar para o usuário, ou None se não configurado."""
    from app.integrations.token_store import get_google_credentials
    creds = await get_google_credentials(user_id)
    return GoogleCalendarClient(credentials_data=creds, user_id=user_id) if creds else None
