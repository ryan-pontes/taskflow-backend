import json
from datetime import datetime, timedelta
from typing import List, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from app.config import settings

class GoogleCalendarClient:
    def __init__(self, credentials_json: str = None):
        self.credentials_json = credentials_json or settings.GOOGLE_CREDENTIALS_JSON
        self._service = None
    
    def _get_service(self, access_token: str):
        """Criar serviço com access token do usuário"""
        credentials = Credentials(token=access_token)
        return build('calendar', 'v3', credentials=credentials)
    
    async def get_events(
        self, 
        access_token: str,
        time_min: datetime = None,
        time_max: datetime = None,
        max_results: int = 50
    ) -> List[dict]:
        """Buscar eventos do calendário"""
        service = self._get_service(access_token)
        
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
        access_token: str,
        date: datetime = None
    ) -> dict:
        """Verificar disponibilidade em uma data"""
        if not date:
            date = datetime.utcnow()
        
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        events = await self.get_events(access_token, start_of_day, end_of_day)
        
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
        access_token: str,
        summary: str,
        start: datetime,
        end: datetime,
        description: str = None,
        attendees: List[str] = None
    ) -> dict:
        """Criar evento no calendário"""
        service = self._get_service(access_token)
        
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
        access_token: str,
        date: datetime,
        start_hour: int,
        duration_hours: int,
        title: str = "🧠 Bloco de Foco"
    ) -> dict:
        """Criar bloco de foco no calendário"""
        start = date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=duration_hours)
        
        return await self.create_event(
            access_token=access_token,
            summary=title,
            start=start,
            end=end,
            description="Bloco de foco criado pelo TaskFlow Manager"
        )


# Singleton
calendar_client = GoogleCalendarClient()
