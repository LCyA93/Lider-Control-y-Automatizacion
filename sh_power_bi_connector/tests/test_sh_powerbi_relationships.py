# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPowerBIRelationships(TransactionCase):
    """Verify the relational field format used for Power BI table relationships.

    Foreign keys must be exported as numeric integer ids so that Power BI can
    build direct primary key / foreign key relationships, optionally accompanied
    by a ``<field>_display`` column carrying the human readable name.
    """

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.company.sh_powerbi_relation_format = 'id_and_display'

        self.partner = self.env['res.partner'].create({
            'name': 'PowerBI Test Customer',
            'email': 'powerbi_test@example.com',
            'company_id': self.company.id,
        })

        self.product_tmpl = self.env['product.template'].create({
            'name': 'PowerBI Test Office Desk',
            'list_price': 450.0,
            'company_id': self.company.id,
        })
        self.product_variant = self.product_tmpl.product_variant_ids[0]

    # ── 1. Core relationship ────────────────────────────────────────────────

    def test_01_product_variant_template_relationship(self):
        """product_tmpl_id must be the integer template id and match product.template.id."""
        variant_data = self.env['product.product'].sh_powerbi_search_read(
            domain=[('id', '=', self.product_variant.id)],
            fields=['id', 'name', 'product_tmpl_id'],
        )
        self.assertTrue(variant_data, "Variant search_read returned empty data.")
        row = variant_data[0]

        self.assertIsInstance(
            row.get('product_tmpl_id'), int,
            "product_tmpl_id must be an integer ID for Power BI relationships.",
        )
        self.assertEqual(
            row.get('product_tmpl_id'), self.product_tmpl.id,
            "product_tmpl_id must match product.template.id.",
        )

        self.assertIn('product_tmpl_id_display', row, "Companion display column must be present.")
        self.assertIn(
            self.product_tmpl.name, row.get('product_tmpl_id_display'),
            "product_tmpl_id_display must contain the template name.",
        )

        tmpl_data = self.env['product.template'].sh_powerbi_search_read(
            domain=[('id', '=', self.product_tmpl.id)],
            fields=['id', 'name'],
        )
        self.assertTrue(tmpl_data, "Template search_read returned empty data.")

        self.assertEqual(
            row['product_tmpl_id'], tmpl_data[0]['id'],
            "Foreign key product_tmpl_id must strictly equal the primary key id.",
        )

    # ── 2. Accounting ───────────────────────────────────────────────────────

    def test_02_account_move_line_relationships(self):
        """Account move line foreign keys must be integer ids."""
        account = self.env['account.account'].search(
            [('company_ids', 'in', self.company.id)], limit=1
        )
        journal = self.env['account.journal'].search(
            [('company_id', '=', self.company.id)], limit=1
        )
        if not account or not journal:
            self.skipTest("Chart of accounts is not loaded for this company")

        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': journal.id,
            'invoice_line_ids': [
                (0, 0, {
                    'name': 'Desk Consultation Line',
                    'quantity': 1,
                    'price_unit': 100.0,
                    'account_id': account.id,
                })
            ],
        })

        lines = self.env['account.move.line'].sh_powerbi_search_read(
            domain=[('move_id', '=', move.id)],
            fields=['id', 'move_id', 'partner_id', 'account_id', 'journal_id', 'company_id'],
        )
        self.assertTrue(lines, "Account move line search_read returned empty data.")
        line = lines[0]

        self.assertIsInstance(line.get('move_id'), int, "move_id must be an integer ID.")
        self.assertEqual(line.get('move_id'), move.id)
        self.assertIsInstance(line.get('journal_id'), int, "journal_id must be an integer ID.")
        self.assertEqual(line.get('journal_id'), journal.id)
        self.assertIsInstance(line.get('account_id'), int, "account_id must be an integer ID.")
        self.assertEqual(line.get('account_id'), account.id)

        self.assertIn('move_id_display', line)
        self.assertIn('journal_id_display', line)
        self.assertIn('move_id_display', line)

    # ── 3. Inventory ────────────────────────────────────────────────────────

    def test_03_stock_move_relationships(self):
        """Stock move foreign keys must be integer ids."""
        picking_type = self.env['stock.picking.type'].search(
            [('company_id', '=', self.company.id)], limit=1
        )
        location = self.env['stock.location'].search(
            [('usage', '=', 'internal'), ('company_id', 'in', [False, self.company.id])], limit=1
        )
        location_dest = self.env['stock.location'].search([('usage', '=', 'customer')], limit=1)

        if not picking_type or not location or not location_dest:
            self.skipTest("No warehouse picking type or location available")

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': location.id,
            'location_dest_id': location_dest.id,
            'partner_id': self.partner.id,
        })
        stock_move = self.env['stock.move'].create({
            'product_id': self.product_variant.id,
            'product_uom_qty': 5,
            'product_uom': self.product_variant.uom_id.id,
            'picking_id': picking.id,
            'location_id': location.id,
            'location_dest_id': location_dest.id,
        })

        moves = self.env['stock.move'].sh_powerbi_search_read(
            domain=[('id', '=', stock_move.id)],
            fields=['id', 'picking_id', 'product_id', 'location_id', 'location_dest_id'],
        )
        self.assertTrue(moves, "Stock move search_read returned empty data.")
        row = moves[0]

        self.assertIsInstance(row.get('picking_id'), int, "picking_id must be integer.")
        self.assertEqual(row.get('picking_id'), picking.id)
        self.assertIsInstance(row.get('product_id'), int, "product_id must be integer.")
        self.assertEqual(row.get('product_id'), self.product_variant.id)
        self.assertIn('product_id_display', row)

    # ── 4. Purchase ─────────────────────────────────────────────────────────

    def test_04_purchase_order_line_relationships(self):
        """Purchase order line foreign keys must be integer ids."""
        supplier = self.env['res.partner'].create({
            'name': 'PowerBI Test Supplier',
            'supplier_rank': 1,
            'company_id': self.company.id,
        })
        po = self.env['purchase.order'].create({
            'partner_id': supplier.id,
            'company_id': self.company.id,
            'order_line': [
                (0, 0, {
                    'name': self.product_variant.name,
                    'product_id': self.product_variant.id,
                    'product_qty': 2.0,
                    'product_uom_id': self.product_variant.uom_id.id,
                    'price_unit': 300.0,
                    'date_planned': '2026-12-01',
                })
            ],
        })

        pol_data = self.env['purchase.order.line'].sh_powerbi_search_read(
            domain=[('order_id', '=', po.id)],
            fields=['id', 'order_id', 'product_id', 'partner_id', 'company_id'],
        )
        self.assertTrue(pol_data, "PO line search_read returned empty data.")
        pol_row = pol_data[0]

        self.assertIsInstance(pol_row.get('order_id'), int, "order_id must be integer.")
        self.assertEqual(pol_row.get('order_id'), po.id)
        self.assertIsInstance(pol_row.get('product_id'), int, "product_id must be integer.")
        self.assertEqual(pol_row.get('product_id'), self.product_variant.id)
        self.assertIn('order_id_display', pol_row)

    # ── 5. Null handling ────────────────────────────────────────────────────

    def test_05_null_foreign_key_handling(self):
        """An unassigned Many2one must be None (JSON null), never "" or 0."""
        standalone = self.env['res.partner'].create({
            'name': 'Standalone Contact',
            'parent_id': False,
            'company_id': self.company.id,
        })
        rows = self.env['res.partner'].sh_powerbi_search_read(
            domain=[('id', '=', standalone.id)],
            fields=['id', 'name', 'parent_id'],
        )
        self.assertTrue(rows)
        row = rows[0]

        self.assertIsNone(
            row.get('parent_id'),
            "Unassigned Many2one field must be None (JSON null).",
        )
        self.assertEqual(
            row.get('parent_id_display'), "",
            "Unassigned companion display field must be an empty string.",
        )

    # ── 6. Relation format modes ───────────────────────────────────────────

    def test_06_format_modes_switching(self):
        """Switching the relation format must switch the output structure."""
        self.company.sh_powerbi_relation_format = 'id_only'
        row_id_only = self.env['product.product'].sh_powerbi_search_read(
            domain=[('id', '=', self.product_variant.id)],
            fields=['id', 'product_tmpl_id'],
        )[0]
        self.assertEqual(row_id_only.get('product_tmpl_id'), self.product_tmpl.id)
        self.assertNotIn('product_tmpl_id_display', row_id_only)

        self.company.sh_powerbi_relation_format = 'display_only'
        row_display_only = self.env['product.product'].sh_powerbi_search_read(
            domain=[('id', '=', self.product_variant.id)],
            fields=['id', 'product_tmpl_id'],
        )[0]
        self.assertEqual(
            row_display_only.get('product_tmpl_id'), self.product_tmpl.display_name,
            "display_only must return the readable name in the foreign key column.",
        )
        self.assertNotIn('product_tmpl_id_display', row_display_only)

        self.company.sh_powerbi_relation_format = 'id_and_display'
        row_both = self.env['product.product'].sh_powerbi_search_read(
            domain=[('id', '=', self.product_variant.id)],
            fields=['id', 'product_tmpl_id'],
        )[0]
        self.assertEqual(row_both.get('product_tmpl_id'), self.product_tmpl.id)
        self.assertEqual(row_both.get('product_tmpl_id_display'), self.product_tmpl.display_name)

    # ── 7. Push schema, default mode ───────────────────────────────────────

    def test_07_push_dataset_schema_generation(self):
        """In id_and_display mode a Many2one is Int64 and gets a String companion."""
        config = self.env['sh.powerbi.push.config'].create({
            'name': 'Test Power BI Config',
            'company_id': self.company.id,
        })
        model_product = self.env['ir.model'].search([('model', '=', 'product.product')], limit=1)
        access = self.env['sh.powerbi.model.access'].create({
            'name': 'Products',
            'config_id': config.id,
            'model_id': model_product.id,
            'company_id': self.company.id,
        })

        columns = config._build_column_schema(access, ['id', 'name', 'product_tmpl_id'])
        col_map = {col['name']: col['dataType'] for col in columns}

        self.assertIn('product_tmpl_id', col_map)
        self.assertEqual(
            col_map['product_tmpl_id'], 'Int64',
            "Foreign key column must be Int64 in the Power BI dataset schema.",
        )
        self.assertIn('product_tmpl_id_display', col_map)
        self.assertEqual(
            col_map['product_tmpl_id_display'], 'String',
            "Companion display column must be String.",
        )

    # ── 8. Client case ──────────────────────────────────────────────────────

    def test_08_client_case_actadm_simulation(self):
        """Reproduce the exact client case reported in Problem identified Power BI.docx."""
        tmpl = self.env['product.template'].create({
            'name': 'ACTADM0001 — OFFICE FURNITURE AND EQUIPMENT',
            'company_id': self.company.id,
            'list_price': 1200.0,
        })
        variant = tmpl.product_variant_ids[0]
        variant.default_code = 'ACTADM0001'

        variants_data = self.env['product.product'].sh_powerbi_search_read(
            domain=[('id', '=', variant.id)],
            fields=['id', 'default_code', 'product_tmpl_id'],
        )
        self.assertTrue(variants_data)
        v_row = variants_data[0]

        self.assertIsInstance(v_row['product_tmpl_id'], int)
        self.assertEqual(v_row['product_tmpl_id'], tmpl.id)
        self.assertEqual(v_row['product_tmpl_id_display'], tmpl.display_name)

        templates_data = self.env['product.template'].sh_powerbi_search_read(
            domain=[('id', '=', tmpl.id)],
            fields=['id', 'name'],
        )
        self.assertTrue(templates_data)
        t_row = templates_data[0]

        self.assertEqual(
            v_row['product_tmpl_id'], t_row['id'],
            "Power BI direct relationship can now be established.",
        )

    # ── 9. Sales ────────────────────────────────────────────────────────────

    def test_09_sale_order_line_relationships(self):
        """Sale order line foreign keys must be integer ids."""
        so = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'order_line': [
                (0, 0, {
                    'name': self.product_variant.name,
                    'product_id': self.product_variant.id,
                    'product_uom_qty': 3.0,
                    'price_unit': 450.0,
                })
            ],
        })
        sol_data = self.env['sale.order.line'].sh_powerbi_search_read(
            domain=[('order_id', '=', so.id)],
            fields=['id', 'order_id', 'product_id', 'order_partner_id'],
        )
        self.assertTrue(sol_data)
        sol_row = sol_data[0]

        self.assertIsInstance(sol_row.get('order_id'), int)
        self.assertEqual(sol_row.get('order_id'), so.id)
        self.assertIsInstance(sol_row.get('product_id'), int)
        self.assertEqual(sol_row.get('product_id'), self.product_variant.id)
        self.assertIn('order_id_display', sol_row)

    # ── 10. x2many fields ───────────────────────────────────────────────────

    def test_10_x2many_comma_separated_ids_and_display(self):
        """One2many fields expose numeric ids plus a companion display column."""
        tmpl_data = self.env['product.template'].sh_powerbi_search_read(
            domain=[('id', '=', self.product_tmpl.id)],
            fields=['id', 'name', 'product_variant_ids'],
        )
        self.assertTrue(tmpl_data)
        t_row = tmpl_data[0]

        self.assertIn(
            str(self.product_variant.id), t_row.get('product_variant_ids', ''),
            "One2many field must expose the related numeric ids.",
        )
        self.assertIn('product_variant_ids_display', t_row)
        self.assertIn(
            self.product_variant.display_name, t_row.get('product_variant_ids_display', ''),
            "One2many companion must expose the related display names.",
        )

    # ── 11. fetch_rows endpoint parity ──────────────────────────────────────

    def test_11_fetch_rows_endpoint_all_modes(self):
        """sh_powerbi_fetch_rows must return the same payload as sh_powerbi_search_read."""
        domain = [('id', '=', self.product_variant.id)]
        fields = ['id', 'product_tmpl_id']

        self.company.sh_powerbi_relation_format = 'id_and_display'
        search_row = self.env['product.product'].sh_powerbi_search_read(
            domain=domain, fields=fields
        )[0]
        fetch_row = self.env['product.product'].sh_powerbi_fetch_rows(
            domain=domain, fields=fields
        )[0]

        self.assertEqual(search_row.keys(), fetch_row.keys(), "Both endpoints must expose the same keys.")
        self.assertIsInstance(fetch_row.get('product_tmpl_id'), int)
        self.assertEqual(fetch_row.get('product_tmpl_id'), self.product_tmpl.id)
        self.assertEqual(
            fetch_row.get('product_tmpl_id_display'), self.product_tmpl.display_name,
            "The companion column must carry the display name, never the numeric id.",
        )
        self.assertNotEqual(
            str(fetch_row.get('product_tmpl_id_display')), str(self.product_tmpl.id),
            "The companion column must not contain the numeric id.",
        )

        self.company.sh_powerbi_relation_format = 'id_only'
        fetch_id_only = self.env['product.product'].sh_powerbi_fetch_rows(
            domain=domain, fields=fields
        )[0]
        self.assertEqual(fetch_id_only.get('product_tmpl_id'), self.product_tmpl.id)
        self.assertNotIn('product_tmpl_id_display', fetch_id_only)

        self.company.sh_powerbi_relation_format = 'display_only'
        fetch_display_only = self.env['product.product'].sh_powerbi_fetch_rows(
            domain=domain, fields=fields
        )[0]
        self.assertEqual(
            fetch_display_only.get('product_tmpl_id'), self.product_tmpl.display_name,
            "display_only must return the display name on every endpoint.",
        )
        self.assertNotIn('product_tmpl_id_display', fetch_display_only)

    # ── 12. Push schema, legacy mode ───────────────────────────────────────

    def test_12_push_schema_display_only_mode(self):
        """In display_only mode a Many2one is String and gets no companion column."""
        self.company.sh_powerbi_relation_format = 'display_only'
        config = self.env['sh.powerbi.push.config'].create({
            'name': 'Test Power BI Config Legacy',
            'company_id': self.company.id,
        })
        model_product = self.env['ir.model'].search([('model', '=', 'product.product')], limit=1)
        access = self.env['sh.powerbi.model.access'].create({
            'name': 'Products Legacy',
            'config_id': config.id,
            'model_id': model_product.id,
            'company_id': self.company.id,
        })

        columns = config._build_column_schema(access, ['id', 'name', 'product_tmpl_id'])
        col_map = {col['name']: col['dataType'] for col in columns}

        self.assertEqual(
            col_map['product_tmpl_id'], 'String',
            "Legacy mode must declare the foreign key as String.",
        )
        self.assertNotIn(
            'product_tmpl_id_display', col_map,
            "Legacy mode must not declare a companion column.",
        )
        self.assertNotIn(
            'product_tmpl_id_display', config._get_powerbi_field_names(access),
            "Legacy mode must not expose a companion field name.",
        )

    # ── 13. Push schema, id_only mode ──────────────────────────────────────

    def test_13_push_schema_id_only_mode(self):
        """In id_only mode a Many2one is Int64 and gets no companion column."""
        self.company.sh_powerbi_relation_format = 'id_only'
        config = self.env['sh.powerbi.push.config'].create({
            'name': 'Test Power BI Config Id Only',
            'company_id': self.company.id,
        })
        model_product = self.env['ir.model'].search([('model', '=', 'product.product')], limit=1)
        access = self.env['sh.powerbi.model.access'].create({
            'name': 'Products Id Only',
            'config_id': config.id,
            'model_id': model_product.id,
            'company_id': self.company.id,
        })

        columns = config._build_column_schema(access, ['id', 'name', 'product_tmpl_id'])
        col_map = {col['name']: col['dataType'] for col in columns}

        self.assertEqual(col_map['product_tmpl_id'], 'Int64')
        self.assertNotIn(
            'product_tmpl_id_display', col_map,
            "id_only mode must not declare a companion column.",
        )
        self.assertNotIn(
            'product_tmpl_id_display', config._get_powerbi_field_names(access),
            "id_only mode must not expose a companion field name.",
        )

    # ── 14. Row slicing keeps the companion ────────────────────────────────

    def test_14_push_row_slicing_with_companions(self):
        """Row slicing must keep a companion column together with its base field."""
        config = self.env['sh.powerbi.push.config'].create({
            'name': 'Test Power BI Config Slicing',
            'company_id': self.company.id,
        })
        rows = [{
            'id': 7,
            'product_tmpl_id': self.product_tmpl.id,
            'product_tmpl_id_display': self.product_tmpl.display_name,
            'name': 'ignored',
        }]
        sliced = config._slice_rows_for_table(rows, ['id', 'product_tmpl_id', 'product_tmpl_id_display'])
        self.assertEqual(len(sliced), 1)
        self.assertIn('product_tmpl_id', sliced[0])
        self.assertIn('product_tmpl_id_display', sliced[0])
        self.assertEqual(sliced[0]['product_tmpl_id'], self.product_tmpl.id)
        self.assertEqual(sliced[0]['product_tmpl_id_display'], self.product_tmpl.display_name)
        self.assertNotIn('name', sliced[0])

    # ── 15. Type aware drift detection ──────────────────────────────────────

    def test_15_schema_drift_datatype_detection(self):
        """Drift detection must see column data type changes."""
        config = self.env['sh.powerbi.push.config'].create({
            'name': 'Test Power BI Config Drift',
            'company_id': self.company.id,
        })
        model_product = self.env['ir.model'].search([('model', '=', 'product.product')], limit=1)
        access = self.env['sh.powerbi.model.access'].create({
            'name': 'Products Drift',
            'config_id': config.id,
            'model_id': model_product.id,
            'company_id': self.company.id,
        })

        odoo_columns = config._get_qualified_schema_columns(access)
        self.assertTrue(odoo_columns)
        self.assertTrue(
            all(':' in column for column in odoo_columns),
            "Qualified schema columns must carry the data type.",
        )

        # Same column names, different data type -> type only drift
        pbi_columns = {column.rsplit(':', 1)[0] + ':String' for column in odoo_columns}
        self.assertTrue(config._sh_powerbi_type_only_drift(odoo_columns, pbi_columns))
        self.assertFalse(config._sh_powerbi_type_only_drift(odoo_columns, odoo_columns))

        # A structural difference is not a type only drift
        pbi_extra = set(pbi_columns) | {'ExtraTable.extra_column:String'}
        self.assertFalse(config._sh_powerbi_type_only_drift(odoo_columns, pbi_extra))

        added, removed, changed = config._sh_powerbi_split_drift(odoo_columns, pbi_columns)
        self.assertFalse(added)
        self.assertFalse(removed)
        self.assertTrue(changed, "A type change must be reported as a changed column.")
        self.assertFalse(
            set(changed) & (set(added) | set(removed)),
            "A changed column must not be double counted as added or removed.",
        )

    # ── 16. Split table adjacency ───────────────────────────────────────────

    def test_16_split_table_pair_adjacency(self):
        """A base field and its companion must never land in different split tables."""
        config = self.env['sh.powerbi.push.config'].create({
            'name': 'Test Power BI Config Split',
            'company_id': self.company.id,
        })
        model_template = self.env['ir.model'].search([('model', '=', 'product.template')], limit=1)
        access = self.env['sh.powerbi.model.access'].create({
            'name': 'Product Templates Split',
            'config_id': config.id,
            'model_id': model_template.id,
            'company_id': self.company.id,
        })

        tables = config._build_powerbi_table_schemas(access)
        self.assertGreater(
            len(tables), 1,
            "product.template is expected to be split into several Power BI tables.",
        )

        owner = {}
        for table in tables:
            for column in table['columns']:
                owner[column['name']] = table['name']

        for column_name in list(owner):
            if not column_name.endswith('_display'):
                continue
            base_name = column_name[:-len('_display')]
            if base_name not in owner:
                continue
            self.assertEqual(
                owner[base_name], owner[column_name],
                f"Column {base_name} and its companion {column_name} must stay in the same table.",
            )

        for table in tables:
            self.assertLessEqual(
                len(table['columns']), 75,
                "Every generated table must respect the 75 column Power BI limit.",
            )

    # ── 17. Display name collision guard ────────────────────────────────────

    def test_17_display_name_collision_guard(self):
        """A real <field>_display column must never be overwritten by the companion."""
        Model = self.env['res.partner']
        # _fields is a read only proxy over the mutable _fields__ mapping
        fields_map = Model._fields__
        self.assertNotIn('parent_id_display', fields_map)

        # Simulate a model that already owns a 'parent_id_display' field
        fields_map['parent_id_display'] = fields_map['name']
        try:
            rows = Model._sh_powerbi_format_rows(
                [{'id': self.partner.id, 'parent_id': self.partner.id}],
                ['id', 'parent_id'],
            )
            self.assertNotIn(
                'parent_id_display', rows[0],
                "The companion must not be emitted when the name is already taken.",
            )
        finally:
            fields_map.pop('parent_id_display', None)

        # Without a collision the companion is emitted normally
        rows = self.env['res.partner']._sh_powerbi_format_rows(
            [{'id': self.partner.id, 'parent_id': self.partner.id}],
            ['id', 'parent_id'],
        )
        self.assertIn('parent_id_display', rows[0])

    # ── 18. Multi company isolation ─────────────────────────────────────────

    def test_18_multi_company_format_isolation(self):
        """Each company must resolve its own relational field format."""
        company_two = self.env['res.company'].create({
            'name': 'PowerBI Test Company Two',
        })
        company_two.sh_powerbi_relation_format = 'display_only'
        self.company.sh_powerbi_relation_format = 'id_and_display'

        format_one = self.env['res.partner']._sh_powerbi_get_relation_format()
        format_two = self.env['res.partner'].with_company(company_two)._sh_powerbi_get_relation_format()

        self.assertEqual(format_one, 'id_and_display')
        self.assertEqual(format_two, 'display_only')

        # The target company binding used by the push queue must be honoured
        bound = self.env['res.partner'].sudo().with_company(company_two)
        self.assertEqual(bound.env.company.id, company_two.id)

        # A background push must use the owning company, not the executing user's
        config = self.env['sh.powerbi.push.config'].create({
            'name': 'Test Power BI Config Multi Company',
            'company_id': company_two.id,
        })
        model_product = self.env['ir.model'].search([('model', '=', 'product.product')], limit=1)
        access = self.env['sh.powerbi.model.access'].create({
            'name': 'Products Multi Company',
            'config_id': config.id,
            'model_id': model_product.id,
            'company_id': company_two.id,
        })
        target_company = access.company_id or config.company_id or self.env.company
        self.assertEqual(target_company.id, company_two.id)

    # ── 19. Background drift must not silently skip the push ────────────────

    def test_19_background_drift_does_not_silently_skip(self):
        """A background push must recreate the dataset instead of returning a wizard."""
        self.company.sh_powerbi_relation_format = 'id_and_display'
        config = self.env['sh.powerbi.push.config'].create({
            'name': 'Test Power BI Config Background',
            'company_id': self.company.id,
            'state': 'authorized',
            'powerbi_workspace_id': '11111111-2222-3333-4444-555555555555',
        })
        model_product = self.env['ir.model'].search([('model', '=', 'product.product')], limit=1)
        access = self.env['sh.powerbi.model.access'].create({
            'name': 'Products Background',
            'config_id': config.id,
            'model_id': model_product.id,
            'company_id': self.company.id,
            'powerbi_dataset_id': 'old-dataset-id',
        })

        odoo_columns = {'Products.product_tmpl_id:Int64'}
        pbi_columns = {'Products.product_tmpl_id:String'}

        log_model = type(self.env['sh.powerbi.log'])
        with patch.object(
            type(config), '_get_schema_diff',
            return_value=(True, odoo_columns, pbi_columns),
        ), patch.object(
            type(config), '_make_powerbi_request',
            return_value=(True, {'id': 'new-dataset-id'}),
        ), patch.object(
            type(self.env['sh.powerbi.push.queue']), 'action_process_queue',
            return_value=True,
        ):
            result = config.with_context(powerbi_background_push=True).action_push_model(access.id)

        self.assertIsInstance(
            result, dict, "The background push must return a notification, not an action.",
        )
        self.assertNotEqual(
            result.get('type'), 'ir.actions.act_window',
            "A background push must not return the schema drift wizard.",
        )
        self.assertEqual(
            access.powerbi_dataset_id, 'new-dataset-id',
            "The dataset must be recreated when the schema changed.",
        )
        self.assertTrue(
            self.env['sh.powerbi.log'].search_count([
                ('model_name', '=', access.model_name),
                ('log_type', '=', 'push'),
            ]),
            "The dataset recreation must be audited in the Power BI log.",
        )
        self.assertTrue(log_model)

    # ── 20. Counters follow the relation format ────────────────────────────

    def test_20_column_counters_follow_relation_format(self):
        """The Power BI column counters must reflect the active relation format."""
        config = self.env['sh.powerbi.push.config'].create({
            'name': 'Test Power BI Config Counters',
            'company_id': self.company.id,
        })
        model_template = self.env['ir.model'].search([('model', '=', 'product.template')], limit=1)
        access = self.env['sh.powerbi.model.access'].create({
            'name': 'Product Templates Counters',
            'config_id': config.id,
            'model_id': model_template.id,
            'company_id': self.company.id,
        })

        self.company.sh_powerbi_relation_format = 'id_and_display'
        access.invalidate_recordset(['powerbi_selected_field_count', 'powerbi_table_count'])
        with_display = access.powerbi_selected_field_count

        # The counter must match the real dataset schema of the same mode
        columns = config._build_column_schema(access)
        self.assertEqual(
            with_display, len(columns),
            "The reported column count must match the generated dataset schema.",
        )

        self.company.sh_powerbi_relation_format = 'id_only'
        access.invalidate_recordset(['powerbi_selected_field_count', 'powerbi_table_count'])
        without_display = access.powerbi_selected_field_count

        self.assertGreater(
            with_display, without_display,
            "The companion display columns must be counted in id_and_display mode.",
        )
        self.assertEqual(
            without_display, len(config._build_column_schema(access)),
            "The reported column count must match the generated dataset schema.",
        )

    # ── 21. fetch_rows and search_rows parity on optional keys ─────────────

    def test_21_optional_foreign_key_parity(self):
        """An empty optional foreign key must behave the same on both endpoints."""
        partner = self.env['res.partner'].create({
            'name': 'Parity Partner',
            'country_id': False,
            'company_id': self.company.id,
        })
        domain = [('id', '=', partner.id)]
        fields = ['id', 'country_id']

        search_row = self.env['res.partner'].sh_powerbi_search_read(domain=domain, fields=fields)[0]
        fetch_row = self.env['res.partner'].sh_powerbi_fetch_rows(domain=domain, fields=fields)[0]

        self.assertEqual(
            search_row.get('country_id'), fetch_row.get('country_id'),
            "Both endpoints must return the same value for an empty foreign key.",
        )
        self.assertIsNone(search_row.get('country_id'))
        self.assertEqual(search_row.get('country_id_display'), "")
