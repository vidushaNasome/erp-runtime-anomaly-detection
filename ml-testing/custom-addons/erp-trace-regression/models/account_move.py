from datetime import timedelta
from odoo import models, api, fields


class AccountMove(models.Model):
    _inherit = "account.move"

    def _trace_user_role(self):
        user = self.env.user
        if user.has_group("account.group_account_manager"):
            return "accountant"
        if user.has_group("account.group_account_user"):
            return "accountant"
        return "user"

    def _get_related_purchase_order(self):
        self.ensure_one()
        if not self.invoice_origin:
            return False

        return self.env["purchase.order"].sudo().search(
            [("name", "=", self.invoice_origin)],
            limit=1,
        )

    def _log_runtime_trace(
        self,
        transaction_id,
        function_name="account.move.write",
        table_name="account.move",
        action="WRITE",
        field_changed=None,
        old_value=None,
        new_value=None,
        trigger_source="orm_write",
        release_version=None,
    ):
        self.env["erp.runtime.trace"].sudo().log_trace(
            transaction_id=transaction_id,
            user_role=self._trace_user_role(),
            module="account",
            function_name=function_name,
            table_name=table_name,
            field_changed=field_changed,
            action=action,
            old_value=str(old_value) if old_value not in [None, False] else False,
            new_value=str(new_value) if new_value not in [None, False] else False,
            trigger_source=trigger_source,
            release_version=release_version,
            flow_id=None,
            label="normal",
            is_anomaly=False,
        )

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)

        for move in moves:
            if move.move_type != "in_invoice":
                continue

            purchase_order = move._get_related_purchase_order()
            if not purchase_order:
                continue

            self.env["erp.runtime.trace"].sudo().log_trace(
                transaction_id=purchase_order.name,
                user_role=move._trace_user_role(),
                module="account",
                function_name="account.move.create",
                table_name="account.move",
                field_changed=None,
                action="CREATE",
                old_value="",
                new_value="",
                trigger_source="orm_create",
            )

            # BUGA2 START:
            # Bill creation incorrectly updates Expected Arrival.
            if self.env.context.get(
                "runtime_scenario"
            ) == "A2_EXPECTED_ARRIVAL_REGRESSION":

                base_date = move.invoice_date or fields.Date.today()
                new_expected_arrival = base_date + timedelta(days=7)

                purchase_order.order_line.sudo().write({
                    "date_planned": new_expected_arrival,
                })

            # BUGA2 END

        return moves
    
    def action_post(self):
        result = super().action_post()

        for move in self:
            if move.move_type != "in_invoice":
                continue

            purchase_order = move._get_related_purchase_order()
            if not purchase_order:
                continue

            self.env["erp.runtime.trace"].sudo().log_trace(
                transaction_id=purchase_order.name,
                user_role=move._trace_user_role(),
                module="account",
                function_name="account.move.action_post",
                table_name="account.move",
                field_changed="state",
                action="WRITE",
                old_value="draft",
                new_value="posted",
                trigger_source="action_post",
            )

        return result

    def write(self, vals):
        tracked_fields = {
            "invoice_date",
            "invoice_date_due",
            "payment_reference",
            "ref",
        }

        old_values = {
            move.id: {
                field: move[field]
                for field in tracked_fields
                if field in vals
            }
            for move in self
            if move.move_type == "in_invoice"
        }

        result = super().write(vals)

        for move in self:
            if move.move_type != "in_invoice":
                continue

            purchase_order = move._get_related_purchase_order()
            transaction_id = (
                purchase_order.name
                if purchase_order
                else move.name or f"BILL-{move.id}"
            )

            for field in tracked_fields:
                if field not in vals:
                    continue

                old_value = old_values.get(move.id, {}).get(field)
                new_value = move[field]

                old_text = old_value.display_name if hasattr(old_value, "display_name") else old_value
                new_text = new_value.display_name if hasattr(new_value, "display_name") else new_value

                if field in ["invoice_date", "invoice_date_due"]:
                    old_text = "SET" if old_text else "EMPTY"
                    new_text = "SET" if new_text else "EMPTY"

                if str(old_text) == str(new_text):
                    continue

                move._log_runtime_trace(
                    transaction_id=transaction_id,
                    field_changed=field,
                    old_value=old_text,
                    new_value=new_text,
                )

        return result