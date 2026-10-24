from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    
    def button_validate(self):
        result = super().button_validate()

        for picking in self:
            if picking.picking_type_code != "incoming":
                continue

            po = picking.purchase_id
            if not po:
                continue

            # Only log completed receipts
            if picking.state != "done":
                continue

            ordered_qty = sum(
                po.order_line.mapped("product_qty")
            )

            received_qty = sum(
                po.order_line.mapped("qty_received")
            )

            if received_qty == 0:
                receipt_bucket = "NONE"
            elif received_qty < ordered_qty:
                receipt_bucket = "PARTIAL"
            elif received_qty == ordered_qty:
                receipt_bucket = "FULL"
            else:
                receipt_bucket = "EXCESS"

            self.env["erp.runtime.trace"].sudo().log_trace(
                transaction_id=po.name,
                user_role="inventory_manager",
                module="stock",
                function_name="stock.picking.button_validate",
                table_name="stock.picking",
                field_changed="receipt_type",
                action="OUTCOME",
                old_value="",
                new_value=receipt_bucket,
                trigger_source="business_outcome",
                release_version=None,
                flow_id=None,
                label="normal",
            )


        # A5BUG: start
        # Goods receipt incorectly changes the purchase order vendor.....
        if self.env.context.get("runtime_scenario") == "A5_VENDOR_CHANGE":

            for picking in self :
                purchase_order = picking.purchase_id

                if not purchase_order:
                    continue

                # Pick a different vendor
                new_vendor = self.env["res.partner"].sudo().search([
                    ("supplier_rank", ">", 0),
                    ("id", "!=", purchase_order.partner_id.id),
                ], limit=1)

                if new_vendor:
                    purchase_order.sudo().write({
                        "partner_id": new_vendor.id
                    })

        return result
        # A5BUG: end

    def write(self, vals):
        tracked_fields    = {
            "scheduled_date",
            "date_deadline" ,
            "state",
            "location_id",
            "location_dest_id",
        }

        changed_fields = tracked_fields.intersection(vals.keys())

        before_values = {}
        if changed_fields :
            for picking in self:
                before_values[picking.id] = {
                    field: picking[field] for field in changed_fields
                }

        result = super().write(vals)

        if changed_fields:
            for picking in self:
                transaction_id = picking.origin or picking.name or f"PICK-{picking.id}"

                for field in changed_fields:
                    self.env["erp.runtime.trace"].sudo().log_trace(
                        transaction_id=   transaction_id,
                        user_role="system",
                        module = "stock",
                        function_name = "stock.picking.write",
                        table_name ="stock.picking",
                        field_changed =field,
                        action ="WRITE",
                        old_value=str(before_values[picking.id].get(field)),
                        new_value=str(picking[field]),
                        trigger_source="automated_method",
                        release_version=None,
                        flow_id=None,
                        label ="normal",
                    )

        return result
