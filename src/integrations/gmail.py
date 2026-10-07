import os

async def execute_gmail_action(action: str, param: str) -> str:
    user = os.getenv("GMAIL_USER")
    password = os.getenv("GMAIL_APP_PASSWORD")
    if not user or not password:
        return "ERRO: Ferramenta do Gmail tentou ser usada, mas GMAIL_USER ou GMAIL_APP_PASSWORD não estão configurados no seu .env."

    try:
        if action == "READ_EMAILS":
            from imap_tools import MailBox, A
            limit = int(param) if param and param.isdigit() else 5
            result = ""
            with MailBox('imap.gmail.com').login(user, password) as mailbox:
                for msg in mailbox.fetch(A(all=True), limit=limit, reverse=True):
                    body_txt = msg.text[:400].replace('\n', ' ')
                    result += f"ID: {msg.uid} | De: {msg.from_} | Assunto: {msg.subject}\nCorpo: {body_txt}...\n\n"
            return result if result else "Caixa de entrada vazia ou erro ao carregar."

        elif action == "SEND_EMAIL":
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            parts = param.split('|', 2)
            if len(parts) != 3:
                return "ERRO: O param deve ser exato no formato 'destinatario | assunto | corpo'"
            to_email, subject, body = [p.strip() for p in parts]

            msg = MIMEMultipart()
            msg['From'] = user
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
            server.quit()
            return f"E-mail enviado com sucesso para {to_email}!"

        elif action == "DELETE_EMAIL":
            from imap_tools import MailBox
            uid = param.strip()
            with MailBox('imap.gmail.com').login(user, password) as mailbox:
                mailbox.delete(uid)
            return f"E-mail referenciado pelo ID {uid} deletado com sucesso e jogado na Lixeira!"

    except Exception as e:
        return f"Exceção Módulo Gmail ({action}): {e}"

    return f"Ação desconhecida do Gmail: {action}"