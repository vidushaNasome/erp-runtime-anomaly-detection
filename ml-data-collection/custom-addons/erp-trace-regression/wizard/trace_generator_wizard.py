import random

from odoo import models, fields
from odoo.exceptions import UserError


class TraceGeneratorWizard(models.TransientModel):
    _name =  "trace.generator.wizard"
    _description = "Runtime Trace Generator Wizard"

    scenario = fields.Selection(
        selection=[
            *[
                (f"n{i}", f"N{i} - Normal Scenario {i}")
                for i in range(1, 6)
            ],
            *[
                (f"a{i}" , f"A{i} - Anomaly Scenario {i}")
                for i in  range(1, 6)
            ],
        ],
        string="Scenario" ,
        required=False,
        default="n1",
    )

    trace_quantity = fields.Integer(
        string="Number of Traces",
        default= 1 ,
        required=True,
    )

    dataset_id = fields.Char(
    string="Dataset ID",
    required=True,
    default="TRAIN_001",
    )

    generation_seed = fields.Integer(
    string="Random Seed",
    default=42,
    )

    variant_id = fields.Char(
    string="Variant",
    default="BASE",
    )

    

    def action_setup_master_data(self):
        self.ensure_one()

        self.env["erp.trace.generator"].setup__master_data()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification" ,
            "params" : {
                "title": "Master Data Ready",
                "message": "Master data created successfully.",
                "type" : "success",
                "sticky": False,
            },
        }

    def action_generate_traces(self):
        self.ensure_one()

        if not self.scenario :
            raise UserError("Please select a scenario.")

        if self.trace_quantity <= 0:
            raise UserError("Number of traces must be greater than 0.")

        generator = self.env["erp.trace.generator"]
        method_name  = f"generate_{self.scenario}"

        generator_method  = getattr(generator, method_name, None)

        if not generator_method:
            raise UserError(
                f"{self.scenario.upper()} is not implemented yet."
            )

        generator_method(
            count=self.trace_quantity,
            dataset_id=self.dataset_id,
            generation_seed=self.generation_seed,
            variant_id=self.variant_id,
        )

        return {
            "type" : "ir.actions.client",
            "tag" : "display_notification",
            "params": {
                "title" : "Traces Generated",
                "message": (
                    f"{self.trace_quantity} trace(s) generated for "
                    f"{self.scenario.upper()}."
                ),
                "type" : "success",
                "sticky": False,
            },
        }
