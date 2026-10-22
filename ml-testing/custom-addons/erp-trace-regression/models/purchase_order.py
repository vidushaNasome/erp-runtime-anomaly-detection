from datetime import timedelta
from odoo import models, api, fields



class PurchaseOrder(models.Model):
    _inherit = "purchase.order"


    # START - Fault injected BUG2-A4

    def button_confirm(self):
        result = super().button_confirm()

        if self.env.context.get(
            "runtime_scenario"
        ) != "A4_PERFORMANCE_REGRESSION" :
            return result

        for po in self:
            for picking in po.picking_ids:
                for move in picking.move_ids :
                    for line in po.order_line :

                        base_date = (
                            line.date_planned
                            or fields.Datetime.now()
                        )

                        for repeat in range(10):
                            line.sudo().write({
                                "date_planned" : (
                                    base_date
                                    + timedelta(days=repeat + 1)
                                ),
                            })

        return result

    # END - Fault injected BUG2-A4

    def action_open_trace_generator_wizard(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Generate Runtime Traces",
            "res_model": "trace.generator.wizard",
            "view_mode": "form",
            "target" : "new",
            "context": {
                "default_purchase_order_id": self.id,
            },
        }


    def _trace_user_role(self):
        user = self.env.user
        if user.has_group("purchase.group_purchase_manager"):
            return "manager"
        if user.has_group("purchase.group_purchase_user"):
            return "purchase_user"
        return "user"

    def _trace_transaction_id(self):
        self.ensure_one()
        return self.name or f"PO-{self.id}"

    def _log_runtime_trace(
        self,
        function_name,
        table_name="purchase.order" ,
        action="WRITE",
        field_changed=None ,
        old_value=None,
        new_value=None,
        trigger_source="orm_write" ,
        release_version=None,
        flow_id=None,
        label="normal",
    ):
        for order in self:
            self.env["erp.runtime.trace"].sudo().log_trace(
                transaction_id=order._trace_transaction_id(),
                user_role=order._trace_user_role(),
                module="purchase" ,
                function_name=function_name ,
                table_name=table_name ,
                field_changed=field_changed,
                action=action,
                old_value=str(old_value) if old_value not in [None, False] else False,
                new_value=str(new_value) if new_value not in [None, False] else False,
                trigger_source=trigger_source,
                release_version=release_version,
                flow_id=flow_id,
                label=label,
                is_anomaly=(label == "anomaly"),
            )

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)

        for order in orders:
            order._log_runtime_trace(
                function_name="purchase.order.create" ,
                action="CREATE" ,
                trigger_source="orm_create",
            )

        return orders

    def write(self, vals):
        tracked_fields = {
            "partner_id",
            "date_order" ,
            "currency_id" ,
            "payment_term_id",
            "fiscal_position_id",
            "state"
        }

        old_values = {
            order.id: {
                field: order[field]
                for field in tracked_fields
                if field in vals
            }
            for order in self
        }

        result = super().write(vals)

        for order in self :
            for field in tracked_fields :
                if field not in vals:
                    continue

                old_value = old_values.get(order.id, {}).get(field)
                new_value = order[field]

                if field ==  "partner_id":
                    old_text  = "EXISTING_VENDOR"
                    new_text = "NEW_VENDOR"
                else:
                    old_text = (
                        old_value.display_name
                        if hasattr(old_value, "display_name")
                        else old_value
                    )

                    new_text = (
                        new_value.display_name
                        if hasattr(new_value, "display_name")
                        else new_value
                    )

                if str(old_text)  == str(new_text):
                    continue

                order._log_runtime_trace(
                    function_name="purchase.order.write",
                    field_changed=field,
                    old_value=old_text,
                    new_value=new_text,
                    action="WRITE",
                    trigger_source="orm_write",
                )

        return result
    