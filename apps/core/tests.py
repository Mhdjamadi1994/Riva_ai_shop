from decimal import Decimal
import hashlib
import hmac
import json
import time
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.contrib import admin
from django.test import RequestFactory
from unittest.mock import MagicMock, patch
from rest_framework.test import APIClient

from apps.core.models import (
    CustomerProfile,
    CustomerSupportTicket,
    ExchangeRate,
    Payment,
    PaymentWebhookEvent,
    WalletTransaction,
)
from apps.products.models import Order, OrderItem, Product


class CustomerAccountPrivacyTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.alex = user_model.objects.create_user(username="alex", password="safe-test-password-1")
        self.blair = user_model.objects.create_user(username="blair", password="safe-test-password-2")
        self.alex_profile = CustomerProfile.objects.get(user=self.alex)
        self.blair_profile = CustomerProfile.objects.get(user=self.blair)
        self.alex_profile.display_name = "Alex Customer"
        self.alex_profile.save()
        self.alex_wallet = self.alex.shop_wallet
        self.blair_wallet = self.blair.shop_wallet
        self.alex_wallet.balance = Decimal("25.00")
        self.alex_wallet.save()
        self.alex_transaction = WalletTransaction.objects.create(
            wallet=self.alex_wallet,
            kind=WalletTransaction.Kind.DEPOSIT,
            status=WalletTransaction.Status.POSTED,
            amount=Decimal("25.00"),
            currency=self.alex_wallet.currency,
        )
        self.blair_transaction = WalletTransaction.objects.create(
            wallet=self.blair_wallet,
            kind=WalletTransaction.Kind.DEPOSIT,
            status=WalletTransaction.Status.POSTED,
            amount=Decimal("90.00"),
            currency=self.blair_wallet.currency,
        )
        product = Product.objects.create(name="Private order product", price=Decimal("10.00"))
        self.alex_order = Order.objects.create(
            user=self.alex,
            full_name="Alex Customer",
            phone="+15550101234",
            address="123 Test Street",
            total_amount=Decimal("10.00"),
        )
        OrderItem.objects.create(order=self.alex_order, product=product, product_name=product.name, unit_price=product.price, quantity=1)
        self.alex_payment = Payment.objects.create(
            user=self.alex,
            order=self.alex_order,
            provider=Payment.Provider.CARD,
            status=Payment.Status.PENDING,
            amount=Decimal("10.00"),
            currency=self.alex_wallet.currency,
        )
        self.client = APIClient()

    def test_account_summary_contains_only_the_signed_in_users_records(self):
        self.client.force_authenticate(user=self.alex)
        response = self.client.get("/api/storefront/account/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["profile"]["username"], "alex")
        self.assertEqual(response.data["profile"]["display_name"], "Alex Customer")
        self.assertEqual(response.data["wallet"]["balance"], Decimal("25.00"))
        self.assertEqual([row["reference"] for row in response.data["transactions"]], [str(self.alex_transaction.reference)])
        self.assertEqual([row["id"] for row in response.data["payments"]], [self.alex_payment.pk])
        self.assertEqual([row["id"] for row in response.data["orders"]], [self.alex_order.pk])

    def test_profile_update_changes_only_the_signed_in_users_profile(self):
        self.client.force_authenticate(user=self.blair)
        response = self.client.patch("/api/storefront/account/profile/", {"display_name": "Blair Customer"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.alex_profile.refresh_from_db()
        self.blair_profile.refresh_from_db()
        self.assertEqual(self.alex_profile.display_name, "Alex Customer")
        self.assertEqual(self.blair_profile.display_name, "Blair Customer")


class SupportEmailActionTests(TestCase):
    @patch("apps.core.admin.send_mail", return_value=1)
    def test_admin_sends_only_staff_approved_reply_and_marks_ticket_sent(self, send_mail_mock):
        user = get_user_model().objects.create_user(
            username="reply-customer", email="customer@example.test", password="safe-test-password"
        )
        ticket = CustomerSupportTicket.objects.create(
            user=user, subject="Product question", message="Please help.", staff_reply="Here is the answer."
        )
        request = RequestFactory().post("/admin/core/customersupportticket/")
        request.user = get_user_model().objects.create_superuser(
            username="reply-admin", email="admin@example.test", password="safe-test-password"
        )
        request._messages = MagicMock()
        model_admin = admin.site._registry[CustomerSupportTicket]

        model_admin.send_approved_replies(request, CustomerSupportTicket.objects.filter(pk=ticket.pk))

        send_mail_mock.assert_called_once()
        self.assertEqual(send_mail_mock.call_args.kwargs["recipient_list"], ["customer@example.test"])
        ticket.refresh_from_db()
        self.assertTrue(ticket.auto_response_sent)


class PricingAndPaymentReliabilityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="payment-buyer", password="safe-test-password")
        self.product = Product.objects.create(name="Payment test item", price=Decimal("2050000"), stock=2)
        self.order = Order.objects.create(
            user=self.user,
            full_name="Payment Buyer",
            phone="+15550123456",
            address="123 Payment Test Street",
            total_amount=Decimal("2050000"),
            quoted_total_usd=Decimal("20.50"),
            status=Order.Status.AWAITING_PAYMENT,
        )
        self.payment = Payment.objects.create(
            user=self.user,
            order=self.order,
            provider=Payment.Provider.CARD,
            status=Payment.Status.PENDING,
            amount=Decimal("20.50"),
            currency="USD",
            provider_reference="cs_test_riva_123",
        )

    @override_settings(
        DEBUG=False,
        DEMO_MODE=True,
        ALLOW_MOCK_PAYMENTS=True,
        PAYMENT_PROVIDER="mock",
        ALLOWED_HOSTS=["testserver"],
    )
    def test_explicit_public_demo_mode_allows_only_simulated_checkout(self):
        self.payment.checkout_token = uuid.uuid4()
        self.payment.save(update_fields=("checkout_token",))

        page = self.client.get(f"/payments/mock/{self.payment.checkout_token}/")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "does not collect card details or charge money")

        response = self.client.post(f"/payments/mock/{self.payment.checkout_token}/")
        self.assertEqual(response.status_code, 302)
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PAID)
        self.assertEqual(self.order.status, Order.Status.PENDING)

    @override_settings(
        DEBUG=False,
        DEMO_MODE=False,
        ALLOW_MOCK_PAYMENTS=True,
        PAYMENT_PROVIDER="mock",
        ALLOWED_HOSTS=["testserver"],
    )
    def test_public_mock_checkout_stays_hidden_when_demo_mode_is_off(self):
        self.payment.checkout_token = uuid.uuid4()
        self.payment.save(update_fields=("checkout_token",))

        response = self.client.get(f"/payments/mock/{self.payment.checkout_token}/")
        self.assertEqual(response.status_code, 404)

    def test_exchange_rate_records_auditable_source_and_timestamp(self):
        from apps.core.pricing import get_usd_toman_quote
        from django.utils import timezone

        observed = timezone.now()
        rate = ExchangeRate.objects.create(rate=Decimal("100000"), source="test-provider", observed_at=observed)
        quote = get_usd_toman_quote(require_fresh=True)
        self.assertEqual(quote.rate, rate.rate)
        self.assertEqual(quote.source, "test-provider")
        self.assertEqual(quote.observed_at, observed)

    @override_settings(
        FX_RATE_PROVIDER_URL="https://rates.example.test/usd-toman",
        FX_RATE_PROVIDER_TOKEN="test-token",
        FX_RATE_PROVIDER_SOURCE="approved-test-provider",
        FX_RATE_MAX_AGE_HOURS=24,
    )
    @patch("apps.core.fx_provider.httpx.get")
    def test_provider_rate_is_audited_and_duplicate_observation_is_idempotent(self, mock_get):
        from apps.core.fx_provider import refresh_usd_toman_rate
        from django.utils import timezone

        observed = timezone.now().isoformat()
        mock_response = mock_get.return_value
        mock_response.json.return_value = {
            "rate": "910000.5",
            "observed_at": observed,
            "source": "provider-response",
        }
        first = refresh_usd_toman_rate()
        second = refresh_usd_toman_rate()

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.rate, Decimal("910000.5"))
        self.assertEqual(first.source, "approved-test-provider")
        self.assertEqual(ExchangeRate.objects.count(), 1)
        self.assertEqual(mock_get.call_args.kwargs["headers"], {"Authorization": "Bearer test-token"})

    @override_settings(FX_RATE_PROVIDER_URL="http://rates.example.test/usd-toman")
    def test_fx_provider_rejects_non_https_url(self):
        from apps.core.fx_provider import FXRateProviderError, refresh_usd_toman_rate

        with self.assertRaises(FXRateProviderError):
            refresh_usd_toman_rate()

    @override_settings(PAYMENT_WEBHOOK_SECRET="test-webhook-secret", PAYMENT_WEBHOOK_TOLERANCE_SECONDS=300)
    def test_signed_duplicate_payment_event_is_only_applied_once(self):
        from apps.core.payments import process_stripe_event, verify_stripe_signature

        payload = json.dumps({
            "id": "evt_riva_reliability_test",
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": self.payment.provider_reference,
                "metadata": {"payment_id": str(self.payment.pk)},
                "payment_status": "paid",
                "amount_total": 2050,
                "currency": "usd",
            }},
        }, separators=(",", ":")).encode()
        timestamp = int(time.time())
        digest = hmac.new(
            b"test-webhook-secret", str(timestamp).encode() + b"." + payload, hashlib.sha256
        ).hexdigest()
        signature = f"t={timestamp},v1={digest}"
        self.assertTrue(verify_stripe_signature(payload, signature))
        self.assertTrue(process_stripe_event(payload))
        self.assertFalse(process_stripe_event(payload))
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PAID)
        self.assertEqual(self.order.status, Order.Status.PENDING)

    @override_settings(PAYMENT_WEBHOOK_SECRET="test-webhook-secret", PAYMENT_WEBHOOK_TOLERANCE_SECONDS=300)
    def test_failed_webhook_attempt_is_audited_and_same_event_can_be_retried(self):
        from apps.core.payments import PaymentGatewayError, process_stripe_event

        retryable_payment = Payment.objects.create(
            user=self.user,
            order=self.order,
            provider=Payment.Provider.WALLET,
            status=Payment.Status.PENDING,
            amount=Decimal("20.50"),
            currency="USD",
            provider_reference="cs_test_retryable_event",
        )
        payload = json.dumps({
            "id": "evt_riva_retryable_reliability_test",
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": retryable_payment.provider_reference,
                "metadata": {"payment_id": str(retryable_payment.pk)},
                "payment_status": "paid",
                "amount_total": 2050,
                "currency": "usd",
            }},
        }, separators=(",", ":")).encode()

        with self.assertRaises(Payment.DoesNotExist):
            process_stripe_event(payload)
        event = PaymentWebhookEvent.objects.get(event_id="evt_riva_retryable_reliability_test")
        self.assertEqual(event.processing_error, "processing_error:DoesNotExist")
        self.assertIsNone(event.processed_at)

        retryable_payment.provider = Payment.Provider.CARD
        retryable_payment.save(update_fields=("provider",))
        self.assertTrue(process_stripe_event(payload))
        self.assertFalse(process_stripe_event(payload))
        event.refresh_from_db()
        retryable_payment.refresh_from_db()
        self.assertIsNotNone(event.processed_at)
        self.assertEqual(event.processing_error, "")
        self.assertEqual(retryable_payment.status, Payment.Status.PAID)
