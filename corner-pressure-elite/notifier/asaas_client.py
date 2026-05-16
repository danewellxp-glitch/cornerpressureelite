import aiohttp
import logging
from datetime import date, timedelta
from typing import Optional, Dict, Tuple

from config import ASAAS_API_KEY, ASAAS_API_URL

logger = logging.getLogger("CPES.AsaasClient")


class AsaasClient:
    """Client para interagir com a API v3 do Asaas."""

    def __init__(self):
        # Garante que a URL base não termina com /
        self.base_url = ASAAS_API_URL.rstrip("/")
        self.headers = {
            "Content-Type": "application/json",
            "access_token": ASAAS_API_KEY,
        }
        if not ASAAS_API_KEY:
            logger.error("ASAAS_API_KEY não configurada! Checkout não funcionará.")

    async def _request(self, method: str, endpoint: str, json: Optional[Dict] = None) -> Optional[Dict]:
        """Faz requisição genérica à API Asaas v3."""
        # Remove barra inicial do endpoint para evitar double-slash
        endpoint = endpoint.lstrip("/")
        url = f"{self.base_url}/{endpoint}"

        logger.debug(f"[Asaas] {method} {url} payload={json}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method, url, headers=self.headers, json=json, timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    text = await response.text()
                    if response.status not in [200, 201]:
                        logger.error(
                            f"[Asaas] ERRO {response.status} em {method} {endpoint}: {text}"
                        )
                        return None
                    try:
                        return await response.json(content_type=None)
                    except Exception:
                        import json as _json
                        return _json.loads(text)
        except aiohttp.ClientConnectorError as e:
            logger.error(f"[Asaas] Falha de conexão com {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"[Asaas] Erro inesperado em {endpoint}: {e}", exc_info=True)
            return None

    async def create_customer(self, name: str, email: str, phone: str, external_id: str, cpf: str = "") -> Optional[str]:
        """Cria ou recupera um cliente no Asaas. Retorna o customer ID."""

        # 1. Buscar cliente existente pelo email
        existing = await self._request("GET", f"customers?email={email}&limit=1")
        if existing and existing.get("data"):
            cid = existing["data"][0]["id"]
            logger.info(f"[Asaas] Cliente existente encontrado: {cid}")
            return cid

        # 2. Criar novo cliente
        payload: Dict = {
            "name": name or "Cliente PressureIQ",
            "email": email,
            "externalReference": str(external_id),
            "notificationDisabled": False,
        }
        # CPF/CNPJ — obrigatório para criar assinaturas
        if cpf:
            clean_cpf = "".join(filter(str.isdigit, str(cpf)))
            if clean_cpf:
                payload["cpfCnpj"] = clean_cpf

        # Telefone (opcional)
        if phone:
            clean_phone = "".join(filter(str.isdigit, str(phone)))
            if clean_phone:
                payload["mobilePhone"] = clean_phone

        data = await self._request("POST", "customers", payload)
        if not data:
            logger.error(f"[Asaas] Falha ao criar cliente para email={email}")
            return None

        cid = data.get("id")
        logger.info(f"[Asaas] Cliente criado: {cid}")
        return cid

    async def create_subscription(
        self,
        customer_id: str,
        value: float,
        description: str,
        external_ref: str,
        billing_type: str = "UNDEFINED",
        success_url: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Cria uma assinatura mensal no Asaas. Retorna (subscription_id, invoice_url).

        billingType="UNDEFINED" permite que o cliente escolha o método de pagamento
        (PIX, Boleto, Cartão). success_url: redirect após pagamento.
        """
        # nextDueDate é obrigatório — usar amanhã para gerar cobrança imediata
        next_due = (date.today() + timedelta(days=1)).isoformat()

        payload: Dict = {
            "customer": customer_id,
            "billingType": billing_type,
            "value": value,
            "nextDueDate": next_due,
            "cycle": "MONTHLY",
            "description": description,
            "externalReference": external_ref,
        }
        if success_url:
            payload["callback"] = {"successUrl": success_url, "autoRedirect": True}

        data = await self._request("POST", "subscriptions", payload)
        if not data:
            return None, None

        sub_id = data.get("id")
        if not sub_id:
            logger.error(f"[Asaas] Assinatura criada mas sem ID: {data}")
            return None, None

        logger.info(f"[Asaas] Assinatura criada: {sub_id}")
        invoice_url = await self._fetch_subscription_invoice_url(sub_id, success_url)
        return sub_id, invoice_url

    async def _fetch_subscription_invoice_url(
        self, sub_id: str, success_url: Optional[str] = None
    ) -> Optional[str]:
        """Retorna a invoiceUrl da primeira cobrança da subscription. Fallback: link genérico."""
        payments = await self._request("GET", f"subscriptions/{sub_id}/payments?limit=1")
        if payments and payments.get("data"):
            first = payments["data"][0]
            payment_id = first.get("id")
            if success_url and payment_id:
                await self._request(
                    "POST",
                    f"payments/{payment_id}",
                    {"callback": {"successUrl": success_url, "autoRedirect": True}},
                )
            invoice_url = first.get("invoiceUrl") or first.get("bankSlipUrl")
            if invoice_url:
                logger.info(f"[Asaas] URL de pagamento obtida: {invoice_url}")
                return invoice_url
        logger.warning(f"[Asaas] Sem invoiceUrl na primeira cobrança da sub {sub_id}")
        return f"https://www.asaas.com/c/{sub_id}"

    async def get_subscription_invoice_url(
        self, sub_id: str, success_url: Optional[str] = None
    ) -> Optional[str]:
        """Recupera a invoiceUrl atual de uma subscription existente (para idempotência)."""
        return await self._fetch_subscription_invoice_url(sub_id, success_url)

    async def get_subscription(self, sub_id: str) -> Optional[Dict]:
        return await self._request("GET", f"subscriptions/{sub_id}")

    async def get_payment(self, payment_id: str) -> Optional[Dict]:
        return await self._request("GET", f"payments/{payment_id}")

    async def approve_by_risk_analysis(self, payment_id: str) -> bool:
        """Aprova manualmente uma cobranca em AWAITING_RISK_ANALYSIS (sandbox/dev).

        No sandbox o Asaas pode segurar cartoes de credito esperando aprovacao
        humana. Este endpoint simula o clique de 'Aprovar' no painel.
        """
        data = await self._request("POST", f"payments/{payment_id}/approveByRiskAnalysis")
        if not data:
            return False
        new_status = data.get("status", "")
        approved = new_status in ("CONFIRMED", "RECEIVED")
        if approved:
            logger.info(f"[Asaas] Payment {payment_id} aprovado via risk analysis (status={new_status})")
        else:
            logger.warning(f"[Asaas] approveByRiskAnalysis retornou status={new_status} para {payment_id}")
        return approved

    async def cancel_subscription(self, sub_id: str) -> bool:
        """Cancela uma assinatura no Asaas. Retorna True se cancelada (ou já estava)."""
        if not sub_id or sub_id.startswith("pending_"):
            return True  # sub local que nem chegou no Asaas, nada a cancelar
        data = await self._request("DELETE", f"subscriptions/{sub_id}")
        if data is None:
            logger.warning(f"[Asaas] Falha ao cancelar sub {sub_id} — pode já estar cancelada")
            return False
        deleted = data.get("deleted") is True or data.get("id") == sub_id
        if deleted:
            logger.info(f"[Asaas] Sub {sub_id} cancelada")
        return deleted
