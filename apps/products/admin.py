from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import InventoryMovement, Order, OrderItem, Product


class ProductAdminForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        from apps.chatbot.security import PromptInjectionDetected, normalize_input

        combined = f"{cleaned.get('name', '')}\n{cleaned.get('description', '')}"
        try:
            normalize_input(combined)
        except (PromptInjectionDetected, ValueError):
            self.add_error(
                "description",
                "\u0645\u062a\u0646 \u06a9\u0627\u0644\u0627 \u0634\u0627\u0645\u0644 \u062f\u0633\u062a\u0648\u0631 \u0645\u0633\u062f\u0648\u062f\u0634\u062f\u0647 \u06cc\u0627 \u0628\u06cc\u0634 \u0627\u0632 \u062d\u062f \u0637\u0648\u0644\u0627\u0646\u06cc \u0627\u0633\u062a.",
            )
        return cleaned


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ("id", "name", "category", "price", "stock", "is_available", "created_at")
    list_filter = ("category", "is_available", "created_at")
    search_fields = ("name", "description")
    readonly_fields = ("stock",)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("product", "product_name", "unit_price", "quantity")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "total_amount", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("id", "user__username", "full_name", "phone")
    readonly_fields = ("user", "full_name", "phone", "address", "total_amount", "created_at", "updated_at")
    inlines = (OrderItemInline,)

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change:
            previous_status = Order.objects.filter(pk=obj.pk).values_list("status", flat=True).first()
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            if obj.status == Order.Status.CANCELLED and previous_status != Order.Status.CANCELLED:
                reservations = InventoryMovement.objects.filter(
                    order=obj, kind=InventoryMovement.Kind.SALE
                ).select_related("product")
                for reservation in reservations:
                    product = Product.objects.select_for_update().filter(pk=reservation.product_id).first()
                    if not product or product.stock is None:
                        continue
                    product.stock += reservation.quantity
                    product.save(update_fields=["stock"])
                    InventoryMovement.objects.create(
                        product=product, order=obj, kind=InventoryMovement.Kind.RETURN,
                        quantity=reservation.quantity, reference=f"order:{obj.pk}",
                        note="Stock released after order cancellation.", created_by=request.user,
                    )


class InventoryMovementAdminForm(forms.ModelForm):
    kind = forms.ChoiceField(choices=(
        (InventoryMovement.Kind.RECEIPT, "Inbound receipt"),
        (InventoryMovement.Kind.ISSUE, "Manual outbound"),
    ))

    class Meta:
        model = InventoryMovement
        fields = ("product", "kind", "quantity", "reference", "note")


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    form = InventoryMovementAdminForm
    list_display = ("created_at", "product", "kind", "quantity", "reference", "created_by")
    list_filter = ("kind", "created_at")
    search_fields = ("product__name", "reference", "note")
    readonly_fields = ("created_by", "created_at", "order")

    def save_model(self, request, obj, form, change):
        if change:
            raise ValidationError("Inventory movement records are immutable; add a correcting movement instead.")
        if obj.quantity < 1:
            raise ValidationError({"quantity": "Quantity must be greater than zero."})
        with transaction.atomic():
            product = Product.objects.select_for_update().get(pk=obj.product_id)
            current_stock = product.stock if product.stock is not None else 0
            if obj.kind == InventoryMovement.Kind.ISSUE:
                if product.stock is None or current_stock < obj.quantity:
                    raise ValidationError({"quantity": "Outbound quantity exceeds known stock."})
                product.stock = current_stock - obj.quantity
            elif obj.kind == InventoryMovement.Kind.RECEIPT:
                product.stock = current_stock + obj.quantity
            else:
                raise ValidationError({"kind": "Choose an inbound receipt or manual outbound movement."})
            product.save(update_fields=["stock"])
            obj.created_by = request.user
            super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
