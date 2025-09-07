# import os, requests

# def _send_template(to: str, phone_id: str, token: str, template: str, text: str) -> None:
#     url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
#     headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
#     data = {
#         "messaging_product": "whatsapp",
#         "to": to,
#         "type": "template",
#         "template": {
#             "name": template,                 # e.g., "hello_world" or "morning_brief"
#             "language": {"code": "en_US"},
#             "components": [
#                 {
#                     "type": "body",
#                     "parameters": [
#                         {"type": "text", "text": text}
#                     ]
#                 }
#             ]
#         }
#     }
#     try:
#         requests.post(url, json=data, headers=headers, timeout=15).raise_for_status()
#     except Exception:
#         # best-effort: ignore failures so Discord still delivers
#         pass

# def _chunks(s: str, n: int):
#     s = s.strip()
#     for i in range(0, len(s), n):
#         yield s[i:i+n]

# def send_whatsapp_brief(full_text: str) -> None:
#     """Send the plaintext brief via a WhatsApp *template* (required for proactive daily messages).
#        If long, split into multiple template sends.
#     """
#     token = os.getenv("WHATSAPP_TOKEN", "")
#     phone_id = os.getenv("WHATSAPP_PHONE_ID", "")
#     to = os.getenv("WHATSAPP_TO_NUMBER", "")
#     template = os.getenv("WHATSAPP_TEMPLATE_NAME", "hello_world")
#     if not (token and phone_id and to and template):
#         return

#     # Conservative chunking; template bodies should stay compact.
#     for part in _chunks(full_text, 900):
#         _send_template(to=to, phone_id=phone_id, token=token, template=template, text=part)
