from odoo import models, api, fields


class ERPRuntimeTrace(models.Model):
    _name = "erp.runtime.trace"
    _description = "ERP Runtime Trace"
    _order = "transaction_id, sequence_no"

    transaction_id =  fields.Char(required=True)
    sequence_no = fields.Integer(required=True)
    timestamp =   fields.Datetime(default=fields.Datetime.now)

    dataset_id = fields.Char(
    string="Dataset ID",
    index=True,
    )

    

    generation_seed = fields.Integer(
    string="Generation Seed",
    index=True,
    )

    variant_id = fields.Char(
    string="Variant ID",
    default="BASE",
    )


    user_role = fields.Char()
    module  = fields.Char()
    function_name = fields.Char(required=True)
    table_name  = fields.Char(required=True)
    field_changed = fields.Char()
    action  = fields.Char(required=True)

    old_value = fields.Char()
    new_value = fields.Char()
    trigger_source = fields.Char()

    release_version =  fields.Char(default=None)
    flow_id = fields.Char(default=None)
    label = fields.Selection(
        [("normal", "Normal"), ("anomaly", "Anomaly")],
        default="normal",
        required=True,
    )
    is_anomaly = fields.Boolean(default=False)

    sequence_token   = fields.Char(compute="_compute_sequence_token", store=True)

    @api.depends(
    "user_role",
    "module",
    "action",
    "table_name",
    "field_changed",
    "old_value",
    "new_value" ,
    )
    def _compute_sequence_token(self):
        for rec in self:
            if rec.old_value and rec.new_value:
                value_part = f"{rec.old_value}>{rec.new_value}"
            else:
                value_part = rec.new_value or rec.old_value or ""

            parts = [
                rec.user_role or "",
                rec.module or "",
                rec.action or "",
                rec.table_name or "",
                rec.field_changed or "",
                value_part,
            ]

            rec.sequence_token =  ":".join(str(p) for p in parts if p not in [False, None, ""])

    @api.model
    def log_trace(self, **kwargs):
        transaction_id = kwargs.get("transaction_id")

        last_trace = self.search(
            [("transaction_id", "=", transaction_id)],
            order="sequence_no desc",
            limit=1,
        )

        kwargs["sequence_no"] = last_trace.sequence_no + 1 if last_trace else 1

        if kwargs.get("label") == "anomaly":
            kwargs["is_anomaly"] = True

        return self.create(kwargs)