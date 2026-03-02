import resend
from app.config import settings

resend.api_key = settings.RESEND_API_KEY

async def send_invite_email(to_email: str, invite_token: str, org_name: str, inviter_name: str):
    """Enviar email de convite para novo membro"""
    invite_url = f"{settings.FRONTEND_URL}/invite/{invite_token}"
    
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>Você foi convidado para o TaskFlow Manager!</h2>
        <p><strong>{inviter_name}</strong> convidou você para fazer parte da equipe <strong>{org_name}</strong>.</p>
        <p>Clique no botão abaixo para criar sua conta e começar:</p>
        <a href="{invite_url}" style="display: inline-block; background-color: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 20px 0;">
            Aceitar Convite
        </a>
        <p style="color: #666; font-size: 14px;">Este convite expira em 7 dias.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 12px;">TaskFlow Manager - Gestão inteligente de times</p>
    </div>
    """
    
    result = resend.Emails.send({
        "from": "TaskFlow <noreply@taskflow.app>",
        "to": [to_email],
        "subject": f"Convite para {org_name} no TaskFlow Manager",
        "html": html
    })
    
    return result


async def send_task_assigned_email(to_email: str, task_title: str, assigner_name: str, due_date: str = None):
    """Notificar membro sobre tarefa atribuída"""
    task_url = f"{settings.FRONTEND_URL}/tasks"
    
    due_info = f"<p><strong>Prazo:</strong> {due_date}</p>" if due_date else ""
    
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>Nova tarefa atribuída a você</h2>
        <p><strong>{assigner_name}</strong> atribuiu uma tarefa para você:</p>
        <div style="background: #f5f5f5; padding: 16px; border-radius: 8px; margin: 16px 0;">
            <h3 style="margin: 0 0 8px 0;">{task_title}</h3>
            {due_info}
        </div>
        <a href="{task_url}" style="display: inline-block; background-color: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
            Ver Tarefa
        </a>
    </div>
    """
    
    result = resend.Emails.send({
        "from": "TaskFlow <noreply@taskflow.app>",
        "to": [to_email],
        "subject": f"Nova tarefa: {task_title}",
        "html": html
    })
    
    return result


async def send_report_email(to_email: str, report_pdf: bytes, period: str):
    """Enviar relatório PDF por email"""
    import base64
    
    pdf_base64 = base64.b64encode(report_pdf).decode('utf-8')
    
    result = resend.Emails.send({
        "from": "TaskFlow <noreply@taskflow.app>",
        "to": [to_email],
        "subject": f"Relatório TaskFlow - {period}",
        "html": f"""
        <div style="font-family: Arial, sans-serif;">
            <h2>Seu relatório está pronto!</h2>
            <p>Segue em anexo o relatório do período: <strong>{period}</strong></p>
        </div>
        """,
        "attachments": [
            {
                "filename": f"relatorio-{period}.pdf",
                "content": pdf_base64
            }
        ]
    })
    
    return result
