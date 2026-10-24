from datetime import datetime, timedelta
import random
from odoo import models, api


class ERPTraceGeneratorGeneralisation(models.AbstractModel):
    _inherit = "erp.trace.generator"
    def _gen_mark_normal(self, po, flow_id, dataset_id, generation_seed, variant):
        self.env['erp.runtime.trace'].sudo().search([
            ('transaction_id', '=', po.name)
        ]).write({
            'flow_id': flow_id, 'label': 'normal', 'is_anomaly': False,
            'dataset_id': dataset_id, 'generation_seed': generation_seed,
            'variant_id': variant, 'release_version': 'V1.0',
        })

    def _gen_order(self, rng, master, origin, line_count=1, qty_min=10):
        manager = master['purchase_manager']
        vendor = rng.choice([master['vendor_a'], master['vendor_b']])
        products = [master['product_1'], master['product_2']]
        order_date = datetime(2026, 1, 1, 9, 0) + timedelta(
            days=rng.randint(0, 60), hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59))
        order_lines = []
        for _ in range(line_count):
            product = rng.choice(products)
            order_lines.append((0, 0, {
                'product_id': product.id,
                'name': product.display_name,
                'product_qty': rng.randint(qty_min, 2000),
                'price_unit': rng.choice([10.0, 12.5, 15.0, 20.0, 25.0]),
                'date_planned': order_date + timedelta(
                    days=self._get_vendor_delay(vendor, product)),
                'product_uom': product.uom_po_id.id or product.uom_id.id,
            }))
        return self.env['purchase.order'].with_user(manager).create({
            'partner_id': vendor.id, 'origin': origin,
            'date_order': order_date, 'order_line': order_lines,
        })

    def _gen_validate_receipt(self, picking, qty):
        if picking.state == 'draft':
            picking.action_confirm()
        if picking.state in ('confirmed', 'waiting', 'assigned'):
            picking.action_assign()
        for move in picking.move_ids_without_package:
            if move.move_line_ids:
                for line in move.move_line_ids:
                    line.write({'quantity': qty})
            else:
                move._set_quantity_done(qty)
        result = picking.button_validate()
        if (isinstance(result, dict)
                and result.get('res_model') == 'stock.backorder.confirmation'):
            wizard = self.env['stock.backorder.confirmation'].with_context(
                result.get('context', {})).create({
                    'pick_ids': [(6, 0, picking.ids)]
                })
            wizard.process()
        return picking

    @api.model
    def generate_g1(self, count, dataset_id, generation_seed, variant_id=None):
        rng = random.Random(generation_seed)
        master = self.setup__master_data()
        manager = master['purchase_manager']
        for product in [master['product_1'], master['product_2']]:
            product.with_user(manager).write({'purchase_method': 'receive'})
        for i in range(1, count + 1):
            po = self._gen_order(rng, master, f'GN1-{dataset_id}-{i}', 1, 10)
            if rng.random() < 0.7:
                po.with_user(manager).print_quotation()
            po.with_user(manager).button_confirm()
            picking = po.picking_ids.filtered(
                lambda p: p.state not in ('done', 'cancel'))[:1]
            if not picking:
                raise ValueError(f'No receipt for {po.name}')
            qty = int(po.order_line[0].product_qty)
            if qty < 2:
                raise ValueError('Partial receipt requires at least 2 units')
            partial_qty = rng.randint(1, qty - 1)
            self._gen_validate_receipt(picking.with_user(manager), partial_qty)
            self._gen_mark_normal(po, 'N1', dataset_id, generation_seed,
                                  variant_id or 'G_N1_PARTIAL_STOP')
        return True

    @api.model
    def generate_g2(self, count, dataset_id, generation_seed, variant_id=None):
        rng = random.Random(generation_seed)
        master = self.setup__master_data()
        manager = master['purchase_manager']
        for i in range(1, count + 1):
            po = self._gen_order(rng, master, f'GN2-{dataset_id}-{i}', 1, 10)
            po.with_user(manager).button_confirm()
            total = int(po.order_line[0].product_qty)
            if total < 4:
                raise ValueError('Three partial receipts require at least 4 units')
            cuts = sorted(rng.sample(range(1, total), 3))
            portions = [cuts[0], cuts[1] - cuts[0], cuts[2] - cuts[1]]
            for qty in portions:
                picking = po.picking_ids.filtered(
                    lambda p: p.state not in ('done', 'cancel'))[:1]
                if not picking:
                    raise ValueError(f'No outstanding picking for {po.name}')
                self._gen_validate_receipt(picking.with_user(manager), qty)
            self._gen_mark_normal(po, 'N2', dataset_id, generation_seed,
                                  variant_id or 'G_N2_THREE_PARTIAL')
        return True

    @api.model
    def generate_g3(self, count, dataset_id, generation_seed, variant_id=None):
        rng = random.Random(generation_seed)
        master = self.setup__master_data()
        manager = master['purchase_manager']
        vendor_a, vendor_b = master['vendor_a'], master['vendor_b']
        for i in range(1, count + 1):
            po = self._gen_order(rng, master, f'GN3-{dataset_id}-{i}', 1, 1)
            current = po.partner_id
            if rng.choice([True, False]):
                po.with_user(manager).print_quotation()
            for _ in range(4):
                current = vendor_b if current == vendor_a else vendor_a
                po.with_user(manager).write({'partner_id': current.id})
                for line in po.order_line:
                    new_date = po.date_order + timedelta(
                        days=self._get_vendor_delay(current, line.product_id))
                    line.with_user(manager).write({'date_planned': new_date})
            self._gen_mark_normal(po, 'N3', dataset_id, generation_seed,
                                  variant_id or 'G_N3_FOUR_CHANGES')
        return True

    @api.model
    def generate_g4(self, count, dataset_id, generation_seed, variant_id=None):
        rng = random.Random(generation_seed)
        master = self.setup__master_data()
        manager = master['purchase_manager']
        users = [master['purchase_user_1'], master['purchase_user_2'], manager]
        for i in range(1, count + 1):
            po = self._gen_order(rng, master, f'GN4-{dataset_id}-{i}', 1, 1)
            current_date = po.order_line[0].date_planned
            for _ in range(5):
                days = rng.choice([-10, -7, -5, -3, -1, 1, 3, 5, 7, 10, 15])
                current_date = max(po.date_order, current_date + timedelta(days=days))
                po.order_line.with_user(rng.choice(users)).write({
                    'date_planned': current_date})
            if rng.random() < 0.7:
                po.with_user(rng.choice(users)).print_quotation()
            self._gen_mark_normal(po, 'N4', dataset_id, generation_seed,
                                  variant_id or 'G_N4_FIVE_RESCHEDULES')
        return True

    @api.model
    def generate_g5(self, count, dataset_id, generation_seed, variant_id=None):
        rng = random.Random(generation_seed)
        master = self.setup__master_data()
        manager = master['purchase_manager']
        for product in [master['product_1'], master['product_2']]:
            product.with_user(manager).write({'purchase_method': 'receive'})
        for i in range(1, count + 1):
            po = self._gen_order(rng, master, f'GN5-{dataset_id}-{i}', 4, 1)
            for line in po.order_line:
                old_qty = int(line.product_qty)
                new_qty = rng.randint(1, 2000)
                while new_qty == old_qty:
                    new_qty = rng.randint(1, 2000)
                line.with_user(manager).write({'product_qty': new_qty})
            po.with_user(manager).button_confirm()
            for picking in po.picking_ids:
                picking = picking.with_user(manager)
                if picking.state == 'draft':
                    picking.action_confirm()
                picking.action_assign()
                for move in picking.move_ids_without_package:
                    move.quantity = move.product_uom_qty
                picking.button_validate()
            action = po.with_user(manager).action_create_invoice()
            bill_id = action.get('res_id') if isinstance(action, dict) else None
            if not bill_id:
                raise ValueError(f'Bill not created for {po.name}')
            bill = self.env['account.move'].with_user(manager).browse(bill_id)
            bill.write({'invoice_date': po.date_order.date()})
            bill.action_post()
            self._gen_mark_normal(po, 'N5', dataset_id, generation_seed,
                                  variant_id or 'G_N5_FOUR_LINES')
        return True
