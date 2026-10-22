from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _trace_user_role(self) :
        user = self.env.user

        if user.has_group("stock.group_stock_manager"):
            return "inventory_manager"
        if user.has_group("stock.group_stock_user") :
            return "inventory_user"
        if user.has_group("purchase.group_purchase_manager") :
            return "purchase_manager"
        if user.has_group("purchase.group_purchase_user"):
            return "purchase_user"

        return "user"

    def write(self, vals) :
        tracked_fields = {
            "state",
        }

        changed_fields = tracked_fields.intersection(vals.keys())

        before_values = {}
        if changed_fields :
            for move in self :
                before_values[move.id] = {
                    field: move[field] for field in changed_fields
                }

        result = super().write(vals)

        if changed_fields :
            for move in self :
                transaction_id = (
                    move.picking_id.origin
                    or move.picking_id.name
                    or f"MOVE-{move.id}"
                )

                for field in changed_fields:
                    self.env["erp.runtime.trace"].sudo().log_trace(
                        transaction_id=transaction_id,
                        user_role=move._trace_user_role(),
                        module= "stock",
                        function_name= "stock.move.write",
                        table_name="stock.move",
                        field_changed= field ,
                        action= "WRITE",
                        old_value= str(before_values[move.id].get(field)),
                        new_value= str(move[field]),
                        trigger_source="automated_method",
                        release_version =None ,
                        flow_id= False ,
                        label = "normal" ,
                    )

        return result