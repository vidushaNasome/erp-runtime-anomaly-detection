from datetime import datetime, timedelta
import random
from odoo import models, api, fields


class ERPTraceGenerator(models.AbstractModel):
    _name = "erp.trace.generator"
    _description =  "ERP Runtime Trace Generator"

    def _get_or_create_user(self, login, name, group_xmlids):
        user = self.env["res.users"].sudo().search(
            [("login", "=", login)],
            limit=1 ,
        )

        groups =  [self.env.ref(xmlid).id for xmlid in group_xmlids]

        if not user :
            user = self.env["res.users"].sudo().create({
                "name" : name,
                "login": login,
                "email" : login,
                "groups_id": [(6, 0, groups)]
            })
        else:
            user.sudo().write({
                "name": name,
                "email":   login,
                "groups_id": [(6, 0, groups)],
            })

        return user

    def _get_or_create_vendor(self, name):
        vendor = self.env["res.partner"].sudo().search(
            [("name", "=", name)],
            limit=1,
        )

        if not vendor:
            vendor = self.env["res.partner"].sudo().create({
                "name": name,
                "supplier_rank" : 1,
                "company_type": "company",
            })

        return vendor

    def _get_or_create_product(self, name, price=10.0):
        product = self.env["product.product"].sudo().search(
            [("name", "=", name)],
            limit=1,
        )

        if not product:
            product = self.env["product.product"].sudo().create({
                "name": name,
                "type": "consu",
                "purchase_ok"  : True,
                "sale_ok": False,
                "standard_price": price,
                "list_price": price + 5.0,
            })
        else:
            product.sudo().write({
                "purchase_ok": True,
                "sale_ok": False ,
                "standard_price": price ,
                "list_price": price + 5.0,
            })

        return product

    def _create_or_update_supplierinfo(self, vendor, product, delay, price):
        supplierinfo = self.env["product.supplierinfo"].sudo().search([
            ("partner_id", "=", vendor.id),
            ("product_tmpl_id", "=", product.product_tmpl_id.id),
        ], limit=1)

        vals = {
            "partner_id": vendor.id,
            "product_tmpl_id": product.product_tmpl_id.id,
            "delay": delay ,
            "min_qty": 1.0 ,
            "price": price,
        }

        if supplierinfo:
            supplierinfo.sudo().write(vals)
        else:
            supplierinfo = self.env["product.supplierinfo"].sudo().create(vals)

        return supplierinfo

    def _get_vendor_delay(self, vendor, product):
        supplierinfo = self.env["product.supplierinfo"].sudo().search([
            ("partner_id", "=", vendor.id),
            ("product_tmpl_id", "=", product.product_tmpl_id.id),
        ], limit=1)

        return supplierinfo.delay if supplierinfo else 0
    

    @api.model
    def setup__master_data(self) :
        purchase_user_1 = self._get_or_create_user(
            "purchase.user1@example.com",
            "Purchase User 1",
            ["purchase.group_purchase_user"],
        )

        purchase_user_2 =  self._get_or_create_user(
            "purchase.user2@example.com",
            "Purchase User 2",
            ["purchase.group_purchase_user"],
        )

        purchase_manager =  self._get_or_create_user(
            "purchase.manager@example.com",
            "Purchase Manager" ,
            ["purchase.group_purchase_manager",
             "account.group_account_manager",
             ],
        )


        vendor_a = self._get_or_create_vendor("Vendor A")
        vendor_b =  self._get_or_create_vendor("Vendor B")

        product_1 =   self._get_or_create_product("Product 1", 10.0)
        product_2 = self._get_or_create_product("Product 2", 20.0)

        self._create_or_update_supplierinfo(
            vendor =vendor_a,
            product=product_1,
            delay= 0,
            price= 10.0,
        )

        self._create_or_update_supplierinfo(
            vendor= vendor_b,
            product= product_1,
            delay=0,
            price=12.0,
        )

        self._create_or_update_supplierinfo(
            vendor= vendor_a,
            product= product_2,
            delay =4,
            price=20.0,
        )

        self._create_or_update_supplierinfo(
            vendor= vendor_b,
            product= product_2,
            delay=20,
            price=22.0,
        )

        return {
            "purchase_user_1": purchase_user_1,
            "purchase_user_2": purchase_user_2,
            "purchase_manager": purchase_manager,
            "vendor_a": vendor_a ,
            "vendor_b": vendor_b,
            "product_1": product_1,
            "product_2": product_2  ,
        }

    # Standard procurement
    @api.model
    def generate_n1(self, count, dataset_id, generation_seed, variant_id):

            rng = random.Random(generation_seed)

            PurchaseOrder = self.env["purchase.order"]
    
            master = self.setup__master_data()
    
            vendors = [master["vendor_a"], master["vendor_b"]]
            products = [master["product_1"], master["product_2"]]
    
            manager = master["purchase_manager"]
    
            for product in products:
                product.with_user(manager).write({
                    "purchase_method": "receive" ,
                })
    
            for i in range(1, count + 1) :
    
                vendor = rng.choice(vendors)
    
                base_date = datetime(2026, 1, 1, 9, 0)
    
                order_date = base_date + timedelta(
                    days=rng.randint(0, 60) ,
                    hours=rng.randint(0, 23) ,
                    minutes=rng.randint(0, 59),
                )
    
                line_count = rng.randint(1, 3)
    
                selected_products = [
                    rng.choice(products)
                    for _ in range(line_count)
                ]
    
                product_delays = [
                    self._get_vendor_delay(vendor, product)
                    for product in selected_products
                ]
    
                min_delay_days = min(product_delays)
                expected_arrival  = order_date + timedelta(days=min_delay_days)
    
                order_lines = []
    
                for product in selected_products:
                    quantity = rng.randint(1, 2000)
                    price = rng.choice([10.0, 12.5, 15.0, 20.0, 25.0])
    
                    order_lines.append((0, 0, {
                        "product_id": product.id,
                        "name": product.display_name,
                        "product_qty" : quantity,
                        "price_unit": price,
                        "date_planned": expected_arrival,
                        "product_uom": product.uom_po_id.id or product.uom_id.id,
                    }))
    
                po = PurchaseOrder.with_user(manager).create({
                    "partner_id": vendor.id,
                    "origin" : f"N1-{i}",
                    "date_order": order_date,
                    "order_line": order_lines,
                })
    
                if rng.random() < 0.7:
                    po.with_user(manager).print_quotation()
    
                po.with_user(manager).button_confirm()
    
                for picking in po.picking_ids :
                    picking.with_user(manager).action_confirm()
                    picking.with_user(manager).action_assign()
    
                    for move in picking.move_ids_without_package :
                        move.with_user(manager).quantity = move.product_uom_qty
    
                    picking.with_user(manager).button_validate()
    
                action  = po.with_user(manager).action_create_invoice()
                bill = self.env["account.move"].with_user(manager).browse(action["res_id"])
    
                bill.with_user(manager).write({
                    "invoice_date": expected_arrival.date(),
                })
    
                bill.with_user(manager).action_post()

                self.env["erp.runtime.trace"].sudo().search([
                    ("transaction_id", "=", po.name)
                ]).write({
                        "flow_id": "N1",
                        "label": "normal",
                        "is_anomaly": False,
                        "dataset_id": dataset_id,
                        "generation_seed": generation_seed,
                        "variant_id": variant_id,
                        "release_version" : "V1.0",
                 })

    
            return True


    # Partial goods receipt
    @api.model
    def generate_n2(self, count, dataset_id, generation_seed, variant_id):

        rng = random.Random(generation_seed)

        PurchaseOrder = self.env["purchase.order"]
        Picking = self.env["stock.picking"]

        master = self.setup__master_data()

        vendors = [master["vendor_a"], master["vendor_b"]]
        products = [master["product_1"], master["product_2"]]

        users = [
            master["purchase_user_1"],
            master["purchase_user_2"],
            master["purchase_manager"],
        ]

        manager = master["purchase_manager"]

        variants = [
            ["V1", "V2", "V3"][i % 3]
            for i in range(count)
        ]
        rng.shuffle(variants)

        for i in range(1, count + 1):

            receipt_variant = variants[i - 1]

            creator_user = rng.choice(users)
            confirmer_user = rng.choice(users)

            vendor = rng.choice(vendors)
            product = rng.choice(products)

            base_date = datetime(2026, 1, 1, 9, 0)

            order_date = base_date + timedelta(
                days=rng.randint(0, 60),
                hours=rng.randint(0, 23),
                minutes=rng.randint(0, 59),
            )

            delay_days = self._get_vendor_delay(vendor, product)
            expected_arrival = order_date + timedelta(days=delay_days)

            ordered_qty = rng.randint(10, 2000)

            po = PurchaseOrder.with_user(creator_user).create({
                "partner_id": vendor.id,
                "origin": f"N2-{i}",
                "date_order": order_date,
                "order_line": [(0, 0, {
                    "product_id": product.id,
                    "name": product.display_name,
                    "product_qty": ordered_qty,
                    "price_unit": rng.choice(
                        [10.0, 12.5, 15.0, 20.0, 25.0]
                    ),
                    "date_planned": expected_arrival,
                    "product_uom": (
                        product.uom_po_id.id or product.uom_id.id
                    ),
                })],
            })

            po.with_user(confirmer_user).button_confirm()

            if receipt_variant == "V1":

                first_qty = rng.randint(1, ordered_qty - 1)
                receipt_quantities = [first_qty]

            elif receipt_variant == "V2":

                first_qty = rng.randint(1, ordered_qty - 2)
                second_qty = rng.randint(
                    1, ordered_qty - first_qty - 1
                )

                receipt_quantities = [
                    first_qty,
                    second_qty,
                ]

            else:

                first_qty = rng.randint(1, ordered_qty - 1)

                receipt_quantities = [
                    first_qty,
                    ordered_qty - first_qty,
                ]

            previous_picking = None

            for receipt_qty in receipt_quantities:

                if previous_picking:

                    picking = Picking.search([
                        ("backorder_id", "=", previous_picking.id),
                        ("state", "not in", ["done", "cancel"]),
                    ], order="id desc", limit=1)

                else:

                    picking = po.picking_ids.filtered(
                        lambda p: p.state not in ["done", "cancel"]
                    )[:1]

                if picking:

                    picking = picking.with_user(manager)

                    if picking.state == "draft":
                        picking.action_confirm()

                    if picking.state in [
                        "confirmed", "waiting", "assigned"
                    ]:
                        picking.action_assign()

                    for move in picking.move_ids_without_package:

                        move_quantity = receipt_qty

                        if move.move_line_ids:

                            for move_line in move.move_line_ids:

                                if "quantity" in move_line._fields:
                                    move_line.write({
                                        "quantity": move_quantity
                                    })

                                elif "qty_done" in move_line._fields:
                                    move_line.write({
                                        "qty_done": move_quantity
                                    })

                        else:

                            move._set_quantity_done(move_quantity)

                    result = picking.button_validate()

                    if (
                        isinstance(result, dict)
                        and result.get("res_model")
                        == "stock.backorder.confirmation"
                    ):

                        wizard = self.env[
                            "stock.backorder.confirmation"
                        ].with_context(
                            result.get("context", {})
                        ).create({
                            "pick_ids": [(6, 0, picking.ids)]
                        })

                        wizard.process()

                    previous_picking = picking

            self.env["erp.runtime.trace"].sudo().search([
                ("transaction_id", "=", po.name)
            ]).write({
                "flow_id": "N2",
                "label": "normal",
                "is_anomaly": False,
                "dataset_id": dataset_id,
                "generation_seed": generation_seed,
                "variant_id": variant_id,
                "release_version" : "V1.0",
            })

        return True


    # Authorised supplier (Vendor) change
    @api.model
    def generate_n3(self, count, dataset_id, generation_seed, variant_id):

            rng = random.Random(generation_seed)
            
            PurchaseOrder = self.env["purchase.order"]
    
            master = self.setup__master_data()
    
            vendor_a = master["vendor_a"]
            vendor_b  = master["vendor_b"]
            products = [master["product_1"], master["product_2"]]
    
            users = [
                master["purchase_user_1"],
                master["purchase_user_2"],
                master["purchase_manager"] ,
            ]
    
            for i in range(1, count + 1):
    
                user = rng.choice(users)
                product = rng.choice(products)
    
                old_vendor, new_vendor = rng.choice([
                    (vendor_a, vendor_b) ,
                    (vendor_b, vendor_a),
                ])
    
                quantity = rng.randint(1, 2000)
                price = rng.choice([10.0, 12.5, 15.0, 20.0, 25.0])
    
                base_date = datetime(2026, 1, 1, 9, 0)
                order_date = base_date + timedelta(
                    days=rng.randint(0, 60),
                    hours=rng.randint(0, 23) ,
                    minutes=rng.randint(0, 59),
                )
    
                delay_days = self._get_vendor_delay(old_vendor, product)
                expected_arrival = order_date + timedelta(days=delay_days)
    
                po = PurchaseOrder.with_user(user).create({
                    "partner_id": old_vendor.id,
                    "origin": f"N3-{i}",
                    "date_order" : order_date,
                    "order_line"  : [(0, 0, {
                        "product_id": product.id,
                        "name": product.display_name,
                        "product_qty": quantity,
                        "price_unit": price,
                        "date_planned": expected_arrival,
                        "product_uom": product.uom_po_id.id or product.uom_id.id,
                    })],
                })
    
                print_stage = rng.choice([
                    "before_changes",
                    "after_changes" ,
                    "never",
                ])
    
                if print_stage == "before_changes":
                    po.with_user(user).print_quotation()
    
                change_count = rng.randint(1, 3)
                current_vendor = old_vendor
    
                for _ in range(change_count):
                    new_vendor = vendor_b if current_vendor == vendor_a else vendor_a
    
                    po.with_user(user).write({
                        "partner_id": new_vendor.id,
                    })
    
                    delay_days = self._get_vendor_delay(new_vendor, product)
                    expected_arrival = order_date + timedelta(days=delay_days)
    
                    po.order_line.with_user(user).write({
                        "date_planned" : expected_arrival ,
                    })
    
                    current_vendor = new_vendor
    
                if print_stage ==  "after_changes":
                        po.with_user(user).print_quotation()

                self.env["erp.runtime.trace"].sudo().search([
                                    ("transaction_id", "=", po.name)
                                ]).write({
                                    "flow_id": "N3",
                                    "label": "normal",
                                    "is_anomaly": False,
                                    "dataset_id": dataset_id,
                                    "generation_seed": generation_seed,
                                    "variant_id": variant_id,
                                    "release_version" : "V1.0",
                                                 })
    
            return True


    # Authorised delivery rescheduling
    @api.model
    def generate_n4(self, count, dataset_id, generation_seed, variant_id):

            rng = random.Random(generation_seed)

            PurchaseOrder = self.env["purchase.order"]
    
            master = self.setup__master_data()
    
            vendors = [master["vendor_a"] , master["vendor_b"]]
            products = [master["product_1"], master["product_2"]]
    
            users = [
                master["purchase_user_1"],
                master["purchase_user_2"],
                master["purchase_manager"],
            ]
    
            for i in range(1, count + 1) :
    
                creator_user = rng.choice(users)
                vendor  = rng.choice(vendors)
                product = rng.choice(products)
    
                base_date = datetime(2026, 1, 1, 9, 0)
    
                order_date = base_date + timedelta(
                    days=rng.randint(0, 60),
                    hours=rng.randint(0, 23),
                    minutes=rng.randint(0, 59),
                )
    
                delay_days = self._get_vendor_delay(vendor, product)
                expected_arrival  = order_date + timedelta(days=delay_days)
    
                po = PurchaseOrder.with_user(creator_user).create({
                    "partner_id": vendor.id,
                    "origin": f"N4-{i}" ,
                    "date_order": order_date ,
                    "order_line": [(0, 0, {
                        "product_id": product.id,
                        "name": product.display_name,
                        "product_qty": rng.randint(1, 2000),
                        "price_unit": rng.choice([10.0, 12.5, 15.0, 20.0, 25.0]),
                        "date_planned" : expected_arrival,
                        "product_uom": product.uom_po_id.id or product.uom_id.id,
                    })],
                })
    
                current_arrival = expected_arrival
                reschedule_count = rng.randint(2, 4)
    
                for _ in range(reschedule_count):
                    reschedule_user = rng.choice(users)
    
                    reschedule_days = rng.choice([
                        -10, -7, -5, -3, -1,
                        1,  3,  5,  7, 10, 15,
                    ])
    
                    new_arrival = current_arrival + timedelta(days=reschedule_days)
    
                    if new_arrival < order_date :
                        new_arrival = order_date
    
                    po.order_line.with_user(reschedule_user).write({
                        "date_planned": new_arrival ,
                    })
    
                    current_arrival = new_arrival
    
                if rng.random() < 0.7:
                    po.with_user(rng.choice(users)).print_quotation()

                self.env["erp.runtime.trace"].sudo().search([
                                    ("transaction_id", "=", po.name)
                                ]).write({
                                    "flow_id": "N4",
                                    "label": "normal",
                                    "is_anomaly": False,
                                    "dataset_id": dataset_id,
                                    "generation_seed": generation_seed,
                                    "variant_id": variant_id,
                                    "release_version": "V1.0",
                                                 })
    
            return True


    # Multi-line procurement with authorised edits
    @api.model
    def generate_n5(self, count, dataset_id, generation_seed, variant_id):

        rng = random.Random(generation_seed)

        PurchaseOrder = self.env["purchase.order"]

        master = self.setup__master_data()

        vendors = [master["vendor_a"], master["vendor_b"]]
        products = [master["product_1"], master["product_2"]]
        manager = master["purchase_manager"]

        for product in products:
            product.with_user(manager).write({
                "purchase_method": "receive",
            })

        for i in range(1, count + 1):

            vendor = rng.choice(vendors)

            base_date = datetime(2026, 1, 1, 9, 0)
            order_date = base_date + timedelta(
                days=rng.randint(0, 60),
                hours=rng.randint(0, 23),
                minutes=rng.randint(0, 59),
            )

           
            line_count = rng.randint(2, 3)

            selected_products = [
                rng.choice(products)
                for _ in range(line_count)
            ]

            order_lines = []

            for product in selected_products:
                delay_days = self._get_vendor_delay(
                    vendor, product
                )
                expected_arrival = order_date + timedelta(
                    days=delay_days
                )

                quantity = rng.randint(1, 2000)
                price = rng.choice(
                    [10.0, 12.5, 15.0, 20.0, 25.0]
                )

                order_lines.append((0, 0, {
                    "product_id": product.id,
                    "name": product.display_name,
                    "product_qty": quantity,
                    "price_unit": price,
                    "date_planned": expected_arrival,
                    "product_uom": (
                        product.uom_po_id.id
                        or product.uom_id.id
                    ),
                }))

           
            po = PurchaseOrder.with_user(manager).create({
                "partner_id": vendor.id,
                "origin": f"N5-{i}",
                "date_order": order_date,
                "order_line": order_lines,
            })

            
            editable_lines = po.order_line.filtered(
                lambda line: line.product_id
            )

            change_count = rng.randint(
                1, len(editable_lines)
            )

            selected_lines = rng.sample(
                list(editable_lines),
                change_count
            )

            for line in selected_lines:
                old_qty = line.product_qty
                new_qty = rng.randint(1, 2000)

                while new_qty == old_qty:
                    new_qty = rng.randint(1, 2000)

                line.with_user(manager).write({
                    "product_qty": new_qty,
                })

            
            po.with_user(manager).button_confirm()

            
            for picking in po.picking_ids:
                picking.with_user(manager).action_confirm()
                picking.with_user(manager).action_assign()

                for move in picking.move_ids_without_package:
                    move.with_user(manager).quantity = (
                        move.product_uom_qty
                    )

                picking.with_user(manager).button_validate()

            
            action = po.with_user(
                manager
            ).action_create_invoice()

            bill_id = action.get("res_id")
            if not bill_id:
                raise ValueError(
                    f"Vendor bill not created for {po.name}"
                )

            bill = self.env["account.move"].with_user(
                manager
            ).browse(bill_id)

            
            bill.with_user(manager).write({
                "invoice_date": order_date.date(),
            })

            bill.with_user(manager).action_post()

            self.env["erp.runtime.trace"].sudo().search([
                                ("transaction_id", "=", po.name)
                            ]).write({
                                "flow_id": "N5",
                                "label": "normal",
                                "is_anomaly": False,
                                "dataset_id": dataset_id,
                                "generation_seed": generation_seed,
                                "variant_id": variant_id,
                                "release_version" : "V1.0",
                                             })

        return True
        

    @api.model
    def generate_a1(self, count, dataset_id, generation_seed, variant_id):

        rng = random.Random(generation_seed)

        PurchaseOrder = self.env["purchase.order"]

        master = self.setup__master_data()

        vendors  = [master["vendor_a"], master["vendor_b"]]
        product_1 = master["product_1"]
        product_2 = master["product_2"]

        users = [
            master["purchase_user_1"],
            master["purchase_user_2"] ,
            master["purchase_manager"],
        ]

        for i in range(1, count + 1):
            user = rng.choice(users)
            vendor = rng.choice(vendors)

            base_date = datetime(2026, 1, 1, 9, 0)

            order_date = base_date + timedelta(
                days=rng.randint(0, 60) ,
                hours=rng.randint(0, 23),
                minutes=rng.randint(0, 59),
            )

            expected_arrival = order_date + timedelta(days=rng.randint(3, 14))

            normal_qty_1 = rng.randint(1, 200)
            normal_qty_2 =  rng.randint(1, 200)

            extreme_qty_1 = rng.randint(5000, 20000)
            extreme_qty_2 =  rng.randint(5000, 20000)

            single_extreme =  rng.choice([True, False])

            if single_extreme:
                if rng.choice([True, False]):
                    qty1 = extreme_qty_1
                    qty2 =  normal_qty_2
                    variant = "A1_SINGLE_EXTREME_P1"
                else:
                    qty1 = normal_qty_1
                    qty2 = extreme_qty_2
                    variant = "A1_SINGLE_EXTREME_P2"
            else:
                qty1 = extreme_qty_1
                qty2 = extreme_qty_2
                variant =  "A1_BOTH_EXTREME"

            po = PurchaseOrder.with_user(user).create({
                "partner_id": vendor.id,
                "origin" : f"{variant}-{i}",
                "date_order": order_date,
                "order_line" : [
                    (0, 0, {
                        "product_id": product_1.id,
                        "name": product_1.name,
                        "product_qty": qty1,
                        "price_unit": rng.choice([10.0, 12.5, 15.0, 20.0, 25.0]),
                        "date_planned": expected_arrival,
                    }),
                    (0, 0, {
                        "product_id": product_2.id,
                        "name": product_2.name,
                        "product_qty": qty2,
                        "price_unit": rng.choice([10.0, 12.5, 15.0, 20.0, 25.0]),
                        "date_planned": expected_arrival,
                    }) ,
                ],
            })

            po.with_user(master["purchase_manager"]).button_confirm()

            self.env["erp.runtime.trace"].sudo().search([
                ("transaction_id", "=", po.name)
            ]).write({
                "flow_id" : "A1",
                "release_version" : "V1.0",
                "label": "anomaly",
                "is_anomaly": True,
                "dataset_id": dataset_id,
                "generation_seed": generation_seed,
                "variant_id": variant_id,
            })

        return True
    
    @api.model
    def generate_a2(self, count, dataset_id, generation_seed, variant_id):

        rng = random.Random(generation_seed)
         
        PurchaseOrder  = self.env["purchase.order"]
        Trace = self.env["erp.runtime.trace"].sudo()

        master  = self.setup__master_data()

        vendors = [master["vendor_a"], master["vendor_b"]]
        products = [master["product_1"], master["product_2"]]

        manager  = master["purchase_manager"]

        for product in products:
            product.with_user(manager).write({
                "purchase_method": "receive",
            })

        for i in range(1, count + 1):

            vendor = rng.choice(vendors)

            base_date  = datetime(2026, 1, 1, 9, 0)

            order_date = base_date + timedelta(
                days=rng.randint(0, 60),
                hours=rng.randint(0, 23),
                minutes=rng.randint(0, 59),
            )

            line_count = rng.randint(1, 3)

            selected_products  = [
                rng.choice(products)
                for _ in range(line_count)
            ]

            product_delays  = [
                self._get_vendor_delay(vendor, product)
                for product in selected_products
            ]

            min_delay_days = min(product_delays)
            expected_arrival = order_date + timedelta(days=min_delay_days)

            order_lines  = []

            for product in selected_products:
                quantity = rng.randint(1, 50)
                price = rng.choice([10.0, 12.5, 15.0])

                order_lines.append((0, 0, {
                    "product_id": product.id,
                    "name": product.display_name,
                    "product_qty": quantity,
                    "price_unit": price,
                    "date_planned": expected_arrival,
                    "product_uom": product.uom_po_id.id or product.uom_id.id,
                }))

            po  = PurchaseOrder.with_user(manager).create({
                "partner_id": vendor.id,
                "origin": f"A2-TRACE-{i}",
                "date_order": order_date,
                "order_line": order_lines,
            })

            if rng.random() < 0.7:
                po.with_user(manager).print_quotation()

            po.with_user(manager).button_confirm()

            for picking in po.picking_ids:
                picking.with_user(manager).action_confirm()
                picking.with_user(manager).action_assign()

                for move in picking.move_ids_without_package:
                    move.with_user(manager).quantity = move.product_uom_qty

                picking.with_user(manager).button_validate()

                # A2 anomaly trigger
                po.with_user(manager).with_context(
                    runtime_scenario="A2_EXPECTED_ARRIVAL_REGRESSION"
                ).action_create_invoice()

            bill = po.invoice_ids[:1]
            if bill:
                bill.with_user(manager).write({
                    "invoice_date": fields.Date.today()
                })

            Trace.search([
                ("transaction_id", "=", po.name),
            ]).write({
                "flow_id": "A2",
                "release_version" : "V1.0",
                "label": "anomaly",
                "is_anomaly": True,
                "dataset_id": dataset_id,
                "generation_seed": generation_seed,
                "variant_id": variant_id,
            })

        return True
    

    @api.model
    def generate_a3(self, count, dataset_id, generation_seed, variant_id):

        rng = random.Random(generation_seed)
        
        PurchaseOrder  = self.env["purchase.order"]
        Trace = self.env["erp.runtime.trace"].sudo()

        master = self.setup__master_data()

        vendors  = [master["vendor_a"], master["vendor_b"]]
        products   = [master["product_1"], master["product_2"]]
        manager = master["purchase_manager"]

        for product in products:
            product.with_user(manager).write({
                "purchase_method": "purchase",
            })

        for i in range(1, count + 1):

            vendor = rng.choice(vendors)

            base_date = datetime(2026, 1, 1, 9, 0)

            order_date = base_date + timedelta(
                days=rng.randint(0, 60),
                hours=rng.randint(0, 23),
                minutes=rng.randint(0, 59),
            )

            line_count =  rng.randint(1, 3)
            selected_products = [
                rng.choice(products)
                for _ in range(line_count)
            ]

            product_delays = [
                self._get_vendor_delay(vendor, product)
                for product in selected_products
            ]

            min_delay_days =  min(product_delays)
            expected_arrival = order_date + timedelta(days=min_delay_days)

            order_lines = []

            for product in selected_products:
                quantity = rng.randint(1, 50)
                price = rng.choice([10.0, 12.5, 15.0])

                order_lines.append((0, 0, {
                    "product_id" : product.id,
                    "name" : product.display_name,
                    "product_qty": quantity,
                    "price_unit": price,
                    "date_planned": expected_arrival,
                    "product_uom": product.uom_po_id.id or product.uom_id.id,
                }))

            po = PurchaseOrder.with_user(manager).create({
                "partner_id" : vendor.id,
                "origin": f"A3-TRACE-{i}",
                "date_order": order_date ,
                "order_line": order_lines,
            })

            if rng.random() < 0.7:
                po.with_user(manager).print_quotation()

            po.with_user(manager).button_confirm()

            action  = po.with_user(manager).action_create_invoice()

            bill = self.env["account.move"].browse(action["res_id"])

            bill.with_user(manager).write({
                "invoice_date": fields.Date.today(),
            })

            if bill.state == "draft" :
                bill.with_user(manager).action_post()

            for picking in po.picking_ids:
                if picking.state not in ("done", "cancel"):
                    picking.with_user(manager).action_confirm()
                    picking.with_user(manager).action_assign()

                    for move in picking.move_ids_without_package:
                        move.with_user(manager).quantity = move.product_uom_qty

                    picking.with_user(manager).button_validate()

            Trace.search([
                ("transaction_id", "=", po.name),
            ]).write({
                "flow_id": "A3",
                "release_version" : "V1.0",
                "label": "anomaly",
                "is_anomaly": True,
                "dataset_id": dataset_id,
                "generation_seed": generation_seed,
                "variant_id": variant_id,
            })

        return True
    

    @api.model
    def generate_a4(self, count, dataset_id, generation_seed, variant_id):

        rng = random.Random(generation_seed)

        PurchaseOrder = self.env["purchase.order"]
        Trace = self.env["erp.runtime.trace"].sudo()

        master = self.setup__master_data()

        vendors  = [master["vendor_a"], master["vendor_b"]]
        products   = [master["product_1"], master["product_2"]]
        manager = master["purchase_manager"]

        for i in range(1, count + 1):

            vendor = rng.choice(vendors)
            product = rng.choice(products)

            po  = PurchaseOrder.with_user(manager).create({
                "partner_id": vendor.id,
                "origin": f"A4-TRACE-{i}",
                "order_line": [(0, 0, {
                    "product_id": product.id,
                    "product_qty": rng.randint(1, 50),
                    "price_unit": rng.choice([10.0, 12.5, 15.0]),
                })],
            })

            po.with_user(manager).with_context(
                runtime_scenario="A4_PERFORMANCE_REGRESSION"
            ).button_confirm()

            picking = po.picking_ids[:1]
            if picking:
                for move in picking.move_ids:
                    move.with_user(manager).quantity = move.product_uom_qty
                picking.with_user(manager).button_validate()

            bill_action = po.with_user(manager).action_create_invoice()
            bill = self.env["account.move"].browse(bill_action.get("res_id"))

            if bill:
                bill.with_user(manager).invoice_date = fields.Date.today()
                bill.with_user(manager).action_post()

            Trace.search([
                ("transaction_id", "=", po.name),
            ]).write({
                "flow_id": "A4",
                "release_version" : "V1.0",
                "label": "anomaly",
                "is_anomaly": True,
                "dataset_id": dataset_id,
                "generation_seed": generation_seed,
                "variant_id": variant_id,
            })

        return True
    
    @api.model
    def generate_a5(self, count, dataset_id, generation_seed, variant_id):
        rng = random.Random(generation_seed)
        
        PurchaseOrder = self.env["purchase.order"]
        Trace = self.env["erp.runtime.trace"].sudo()

        master = self.setup__master_data()

        vendors = [master["vendor_a"], master["vendor_b"]]
        products  = [master["product_1"], master["product_2"]]

        users = [
            master["purchase_user_1"],
            master["purchase_user_2"],
            master["purchase_manager"],
        ]

        manager = master["purchase_manager"]

        for i in range(1, count + 1) :

            user = rng.choice(users)
            vendor = rng.choice(vendors)
            product = rng.choice(products)

            order_date = fields.Datetime.now() + timedelta(
                days=rng.randint(0, 60),
                hours=rng.randint(0, 23),
                minutes=rng.randint(0, 59),
            )

            expected_arrival = order_date + timedelta(
                days=rng.randint(3, 14)
            )

            normal_qty = rng.randint(10, 150)
            normal_price = rng.randint(50, 300)

            po = PurchaseOrder.with_user(user).create({
                "partner_id": vendor.id,
                "origin": f"A5-TRACE-{i}",
                "date_order": order_date,
                "order_line": [(0, 0, {
                    "product_id": product.id,
                    "name": product.name,
                    "product_qty": normal_qty,
                    "price_unit": normal_price,
                    "date_planned": expected_arrival,
                })],
            })

            po.with_user(manager).button_confirm()

            
            for picking in po.picking_ids:
                picking.with_user(manager).with_context(
                    runtime_scenario="A5_VENDOR_CHANGE"
                ).button_validate()

            bill_action = po.with_user(manager).action_create_invoice()
            bill = self.env["account.move"].browse(
                bill_action.get("res_id")
            )

            if bill:
                if not bill.invoice_date:
                    bill.invoice_date = fields.Date.today()

                bill.with_user(manager).action_post()

       
            Trace.search([
                ("transaction_id", "=", po.name),
            ]).write({
                "flow_id": "A5",
                "release_version": "A5 Vendor Change Regression/Unexpected Supplier Reassignment Regression",
                "label" : "anomaly" ,
                "is_anomaly" : True,
                "dataset_id": dataset_id,
                "generation_seed": generation_seed,
                "variant_id": variant_id,
            })       