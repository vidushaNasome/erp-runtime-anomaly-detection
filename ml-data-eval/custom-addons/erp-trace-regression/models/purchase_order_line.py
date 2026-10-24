from odoo import models, api


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def _trace_user_role(self):
        user  = self.env.user
        if user.has_group("purchase.group_purchase_manager"):
            return "manager"
        if user.has_group("purchase.group_purchase_user"):
            return "purchase_user"
        return "user"

    def _trace_transaction_id(self):
        self.ensure_one()
        return self.order_id.name or f"PO-{self.order_id.id}"

    def _get_quantity_bucket(self, qty):
        qty = float(qty or 0)

        if qty  <= 100:
            return "LOW"
        elif qty  <= 500:
            return "MEDIUM"
        elif qty <= 2000:
            return "HIGH"
        return "EXTREME"

    def  _get_price_bucket(self, price):
        price = float(price or 0)

        if price <= 12.5:
            return "LOW"
        elif price <= 20.0:
            return "MEDIUM"
        return "HIGH"

    def _get_lead_time_bucket(self, date_order, date_planned):
        if not date_order or not date_planned:
            return "UNKNOWN"

        diff_days = (date_planned - date_order).days

        if diff_days == 0 :
            return "NO_DELAY"
        elif diff_days <= 4:
            return "SHORT_DELAY"
        elif diff_days <= 20:
            return "LONG_DELAY"
        return "EXTRA_LONG_DELAY"

    def _normalise_trace_value(self, field_name, value) :
        if field_name == "product_qty":
            return self._get_quantity_bucket(value)

        if field_name == "price_unit":
            return self._get_price_bucket(value)

        if hasattr(value, "display_name"):
            return value.display_name

        return value

    def _log_runtime_trace(
        self,
        function_name,
        action="WRITE",
        field_changed=None,
        old_value=None,
        new_value=None,
        trigger_source="orm_write",
        release_version=None,
        flow_id=None,
        label="normal",
    ):
        for line in self:
            self.env["erp.runtime.trace"].sudo().log_trace(
                transaction_id=line._trace_transaction_id(),
                user_role=line._trace_user_role(),
                module="purchase",
                function_name=function_name,
                table_name="purchase.order.line",
                field_changed=field_changed,
                action=action ,
                old_value=str(old_value) if old_value not in [None, False] else False,
                new_value=str(new_value) if new_value not in [None, False] else False,
                trigger_source=trigger_source,
                release_version=release_version ,
                flow_id=flow_id ,
                label=label ,
                is_anomaly=False ,
            )

    @api.model_create_multi
    def create(self, vals_list):
        lines =  super().create(vals_list)

        for line in lines:
            line._log_runtime_trace(
                function_name="purchase.order.line.create",
                action="CREATE",
                field_changed="product_qty",
                new_value=line._get_quantity_bucket(line.product_qty),
                trigger_source="orm_create",
            )

            line._log_runtime_trace(
                function_name="purchase.order.line.create",
                action="CREATE" ,
                field_changed="price_unit",
                new_value=line._get_price_bucket(line.price_unit),
                trigger_source="orm_create" ,
            )

            line._log_runtime_trace(
                function_name="purchase.order.line.create",
                action="CREATE" ,
                field_changed="date_planned" ,
                new_value= line._get_lead_time_bucket(
                    line.order_id.date_order ,
                    line.date_planned,
                ),
                trigger_source="orm_create",
            )

        return lines

    def write(self, vals):
        tracked_fields = {
            "date_planned",
            "product_qty" ,
            "price_unit",
            "product_id" ,
        }

        old_values = {
            line.id: {
                field: line[field]
                for field in tracked_fields
                if field in vals
            }
            for line in self
        }

        result = super().write(vals)

        for line in self:
            for field in tracked_fields :
                if field not in vals:
                    continue

                old_value = old_values.get(line.id, {}).get(field)
                new_value = line[field]

                if field ==   "date_planned":
                    old_text = line._get_lead_time_bucket(
                        line.order_id.date_order ,
                        old_value,
                    )
                    new_text = line._get_lead_time_bucket(
                        line.order_id.date_order,
                        new_value,
                    )

                    log_field = "date_planned"

                elif field ==  "product_id" :
                    old_text = "EXISTING_PRODUCT"
                    new_text =   "REPLACED"
                    log_field = "product"

                else:
                    old_text =  line._normalise_trace_value(field, old_value)
                    new_text =  line._normalise_trace_value(field, new_value)
                    log_field =  field

                if str(old_text) ==  str(new_text):
                    continue

                line._log_runtime_trace (
                    function_name="purchase.order.line.write",
                    field_changed= log_field,
                    old_value=old_text,
                    new_value=new_text,
                    action="WRITE",
                    trigger_source="orm_write",
                )
        return result

    def unlink(self):
        unlink_data = []

        for line in self:
            unlink_data.append({
                "transaction_id": line._trace_transaction_id() ,
                "user_role": line._trace_user_role(),
                "product": line.product_id.display_name if line.product_id else False,
                "quantity_bucket" :  line._get_quantity_bucket(line.product_qty),
                "price_bucket":  line._get_price_bucket(line.price_unit) ,
                "lead_time_bucket": line._get_lead_time_bucket(
                    line.order_id.date_order,
                    line.date_planned,
                ),
            })

        result = super().unlink()

        for data in unlink_data  :
            self.env["erp.runtime.trace"].sudo().log_trace(
                transaction_id=data["transaction_id"],
                user_role=data["user_role"],
                module="purchase",
                function_name="purchase.order.line.unlink",
                table_name="purchase.order.line",
                field_changed="order_line",
                action="DELETE",
                old_value=(
                    f"{data['product']} / "
                    f"qty={data['quantity_bucket']} / "
                    f"price={data['price_bucket']} / "
                    f"lead_time={data['lead_time_bucket']}"
                ),
                new_value=False,
                trigger_source="orm_unlink",
                release_version=None,
                flow_id=None ,
                label="normal" ,
                is_anomaly=False 
            )

        return result