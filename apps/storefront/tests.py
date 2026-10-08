from decimal import Decimal

from django.test import TestCase, override_settings

from apps.products.models import Product


class StorefrontCurrencyDisplayTests(TestCase):
    @override_settings(TOMAN_PER_USD=Decimal("20000"))
    def test_product_detail_displays_toman_price_as_usd(self):
        product = Product.objects.create(
            name="Riva display test product", category="monitors", price=Decimal("20800000.00"), stock=2
        )

        response = self.client.get(f"/products/{product.pk}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "$1040.00 USD")
        self.assertContains(response, 'data-toman-per-usd="20000"')
