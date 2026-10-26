# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

import ast
import time
import logging

from odoo import models, api
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


class SHBaseReadMixin(models.BaseModel):
    _inherit = 'base'

    @api.model
    def _sh_powerbi_parse_domain(self, domain):
        """Normalize an incoming domain coming from JSON-2 or legacy config."""
        if not domain:
            return []
        if isinstance(domain, str):
            try:
                domain = ast.literal_eval(domain)
            except Exception as err:
                raise ValidationError(f"Invalid Power BI domain: {err}") from err
        if not isinstance(domain, list):
            raise ValidationError("Power BI domain must be a list.")
        return domain

    @api.model
    def _sh_powerbi_get_model_access(self):
        """Return the active Power BI config for the current model and company."""
        return self.env['sh.powerbi.model.access'].sudo().search([
            ('company_id', '=', self.env.company.id),
            ('model_name', '=', self._name),
            ('is_active', '=', True),
        ], order='sequence, id', limit=1)

    @api.model
    def _sh_powerbi_resolve_fields(self, requested_fields=None):
        """Apply configured allowlist and remove unsupported fields."""
        model_access = self._sh_powerbi_get_model_access()
        configured = []
        if model_access and model_access.allowed_field_ids:
            configured = [field.name for field in model_access.allowed_field_ids if field.name in self._fields]

        if requested_fields:
            requested_fields = [name for name in requested_fields if name in self._fields]
        else:
            requested_fields = configured or [
                name for name, field in self._fields.items()
                if field.store and field.type not in ('binary', 'html', 'json', 'properties', 'properties_definition')
            ]

        if configured:
            allowed = set(configured) | {'id'}
            requested_fields = [name for name in requested_fields if name in allowed]

        if 'id' not in requested_fields:
            requested_fields.append('id')
        return requested_fields

    @api.model
    def _sh_powerbi_apply_access_rules(self, domain=None, fields=None):
        """Enforce company-level Power BI model/field/domain restrictions."""
        company = self.env.company
        domain = self._sh_powerbi_parse_domain(domain)
        fields = list(fields or [])
        fetch_mode = getattr(company, 'sh_powerbi_fetch_mode', 'all') or 'all'
        model_access = self._sh_powerbi_get_model_access()

        if fetch_mode == 'configured' and not model_access:
            raise AccessError(f'Model {self._name} is not enabled for Power BI access.')

        if model_access:
            fields = self._sh_powerbi_resolve_fields(fields)
            config_domain = self._sh_powerbi_parse_domain(model_access.domain_filter)
            if config_domain:
                domain += config_domain
        else:
            fields = self._sh_powerbi_resolve_fields(fields)

        return model_access, domain, fields

    @api.model
    def _sh_powerbi_get_relation_format(self, model_access=None):
        """Return the relational field format configured for the target company.

        The format is resolved from the company that owns the Power BI model
        access configuration so that a background push never inherits the
        executing user's company settings.
        """
        if model_access is None:
            model_access = self._sh_powerbi_get_model_access()
        target_company = (model_access.company_id if model_access else False) or self.env.company
        return getattr(target_company, 'sh_powerbi_relation_format', 'id_and_display') or 'id_and_display'

    @api.model
    def _sh_powerbi_display_value(self, value):
        """Normalise a display name so Power BI always receives a string.

        ``display_name`` can legitimately be False when the related record has no
        readable name, and it must never be exposed as a boolean or as the
        numeric id.
        """
        if value is None or value is False:
            return ""
        if isinstance(value, str):
            return value
        return str(value)

    @api.model
    def _sh_powerbi_format_rows(self, data, fields, model_access=None):
        """Flatten relational values so Power BI receives scalar-friendly JSON.

        Many2one fields expose the numeric foreign key so that Power BI can build
        direct primary-key / foreign-key relationships. Depending on the company's
        relational field format, a companion ``<field>_display`` column carries
        the human readable name.
        """
        if not data:
            return []

        relation_format = self._sh_powerbi_get_relation_format(model_access)

        rel_ids_map = {}
        fields_to_process = []
        for name in fields:
            field = self._fields.get(name)
            if field and field.type in ['many2one', 'one2many', 'many2many']:
                fields_to_process.append(name)
                rel_ids_map[name] = set()

        rel_names_lookup = {}
        if fields_to_process:
            for row in data:
                for name in fields_to_process:
                    val = row.get(name)
                    if not val:
                        continue
                    if isinstance(val, tuple):
                        # Many2one returned as (id, name) - only the id is an identifier
                        rel_ids_map[name].add(val[0])
                    elif isinstance(val, list):
                        rel_ids_map[name].update(val)
                    elif isinstance(val, int):
                        rel_ids_map[name].add(val)

            for name in fields_to_process:
                field = self._fields[name]
                if not rel_ids_map[name]:
                    continue
                related_model = self.env[field.comodel_name]
                names_data = related_model.browse(list(rel_ids_map[name])).read(['display_name'])
                rel_names_lookup[name] = {item['id']: item['display_name'] for item in names_data}

        for row in data:
            for name in list(row.keys()):
                field = self._fields.get(name)
                if not field:
                    continue
                val = row[name]

                if val in (None, False):
                    if field.type == 'boolean':
                        row[name] = False
                    elif field.type in ['integer', 'float', 'monetary', 'many2one']:
                        row[name] = None
                        if field.type == 'many2one' and relation_format == 'id_and_display':
                            disp_name = f"{name}_display"
                            if disp_name not in self._fields:
                                row[disp_name] = ""
                    else:
                        row[name] = ""
                    continue

                if field.type == 'many2one':
                    disp_name = f"{name}_display"
                    can_emit_display = disp_name not in self._fields
                    lookup = rel_names_lookup.get(name, {})
                    if relation_format == 'id_and_display':
                        if isinstance(val, tuple):
                            row[name] = val[0]
                            if can_emit_display:
                                row[disp_name] = self._sh_powerbi_display_value(val[1])
                        elif isinstance(val, int):
                            row[name] = val
                            if can_emit_display:
                                row[disp_name] = self._sh_powerbi_display_value(lookup.get(val))
                        else:
                            row[name] = None
                            if can_emit_display:
                                row[disp_name] = ""
                    elif relation_format == 'id_only':
                        row[name] = val[0] if isinstance(val, tuple) else (val if isinstance(val, int) else None)
                    else:  # display_only
                        if isinstance(val, tuple):
                            row[name] = self._sh_powerbi_display_value(val[1])
                        elif isinstance(val, int):
                            row[name] = self._sh_powerbi_display_value(lookup.get(val))
                        else:
                            row[name] = ""
                elif field.type in ['one2many', 'many2many']:
                    lookup = rel_names_lookup.get(name, {})
                    names_list = [lookup.get(rel_id, '') for rel_id in val if lookup.get(rel_id)]
                    if relation_format in ('id_and_display', 'id_only'):
                        row[name] = ", ".join(str(rid) for rid in val) if isinstance(val, (list, tuple)) else str(val or "")
                        if relation_format == 'id_and_display':
                            disp_name = f"{name}_display"
                            if disp_name not in self._fields:
                                row[disp_name] = ", ".join(names_list)
                    else:  # display_only
                        row[name] = ", ".join(names_list)
                elif field.type == 'selection':
                    try:
                        row[name] = dict(field.selection).get(val, str(val))
                    except Exception:
                        row[name] = str(val)
                elif field.type == 'binary':
                    row.pop(name, None)
                elif hasattr(val, 'isoformat'):
                    row[name] = val.isoformat()
                elif field.type not in ['boolean', 'integer', 'float', 'monetary']:
                    row[name] = str(val)
        return data

    @api.model
    def sh_powerbi_search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """
        Custom optimized search_read for Power BI.
        - Fetches data in batches.
        - Flattens Many2one, One2many, Many2many fields efficiently (O(1) relative to records).
        - Returns a list of dictionaries compatible with search_read.
        """
        start = time.time()

        # ── Configured-mode enforcement (v19.0.3.0.0) ────────────────────────
        # When the company has restricted Power BI to configured models only,
        # enforce field and domain restrictions server-side.
        company = self.env.company
        fetch_mode = getattr(company, 'sh_powerbi_fetch_mode', 'all') or 'all'
        model_access = self._sh_powerbi_get_model_access()
        if fetch_mode == 'configured':
            if not model_access:
                # Model not in the allowlist — block access silently
                return []
            # Restrict fields to the configured allowlist (if any were specified)
            if model_access.allowed_field_ids:
                allowed = {f.name for f in model_access.allowed_field_ids} | {'id'}
                if fields:
                    fields = [f for f in fields if f in allowed]
                else:
                    fields = list(allowed)
            # AND the configured domain filter onto the incoming domain
            if model_access.domain_filter and model_access.domain_filter.strip() not in ('[]', ''):
                try:
                    config_domain = ast.literal_eval(model_access.domain_filter)
                    domain = (domain or []) + config_domain
                except Exception:
                    pass
        # ─────────────────────────────────────────────────────────────────────

        # Custom optimized search_read for Power BI
        self = self.sudo()
        records = self.search(domain or [], offset=offset, limit=limit or False, order=order)
        if not records:
            return []

        fields = self._sh_powerbi_resolve_fields(fields)

        # HYBRID STRATEGY: 
        # Check if we can use Raw SQL (Fastest) or need ORM (Robust for relations)
        can_use_sql = True
        simple_stored_fields = []
        selection_fields = {}
        
        for name in fields:
            if name not in self._fields:
                continue
            field = self._fields[name]
            
            # Criteria for SQL: Stored, NOT Relational, and NOT Translated
            # Translated fields (JSONB in Odoo 17/18) need ORM to extract the correct language
            if not field.store or field.translate or field.type in ['many2one', 'one2many', 'many2many', 'reference', 'binary']:
                can_use_sql = False
                break
            
            # Map column name (usually same as field name)
            simple_stored_fields.append(name)
            
            if field.type == 'selection':
                selection = field.selection
                if callable(selection):
                    try:
                        selection = selection(self)
                    except Exception:
                        selection = []
                selection_fields[name] = dict(selection or [])

        # --- PATH 1: DIRECT SQL (Turbo Mode) ---
        # Only simple stored fields. Skip ORM instantiation.
        if can_use_sql and simple_stored_fields:
            placeholders = ','.join(['%s'] * len(records))
            # Safe column injection because we verified names against self._fields keys
            cols = '","'.join(simple_stored_fields)
            
            query = f'SELECT "{cols}" FROM "{self._table}" WHERE id IN ({placeholders})'
            self.env.cr.execute(query, tuple(records.ids))
            sql_data = self.env.cr.dictfetchall()
            
            # SQL returns raw keys for selections and native types for others.
            # We just need to handle Selection labels and ensure general JSON compatibility.
            if selection_fields:
                for row in sql_data:
                    for name, selection_map in selection_fields.items():
                        if row.get(name):
                             # Map key to label, default to key if not found
                            row[name] = selection_map.get(row[name], row[name])
            
            # Ensure "False" / None becomes "" for consistency with Power BI expectations
            for row in sql_data:
                for key, val in row.items():
                    field = self._fields.get(key)
                    if not field: continue
                    if val is None or val is False:
                        if field.type == 'boolean':
                            row[key] = False
                        elif field.type in ['integer', 'float', 'monetary']:
                            row[key] = None
                        else:
                            row[key] = ""
                    elif hasattr(val, 'isoformat'):
                        row[key] = val.isoformat()

            _logger.debug("sh_powerbi_search_read [SQL] %s: %d records in %.1fms",
                          self._name, len(sql_data), (time.time() - start) * 1000)
            return sql_data

        # --- PATH 2: OPTIMIZED ORM (Relational Mode) ---
        # 1. Standard read (returns (id, name) tuples for relational fields)
        data = records.read(fields)

        # 2. Flatten relational values through the shared formatter so that every
        #    extraction endpoint returns an identical payload shape.
        data = self._sh_powerbi_format_rows(data, fields, model_access)

        _logger.debug("sh_powerbi_search_read [ORM] %s: %d records in %.1fms",
                      self._name, len(data), (time.time() - start) * 1000)
        return data

    # ── Real-Time Push on Record Save (Feature 2) ─────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.cr.postcommit.add(lambda: records._sh_powerbi_queue_realtime())
        return records

    def write(self, vals):
        res = super().write(vals)
        self.env.cr.postcommit.add(lambda: self._sh_powerbi_queue_realtime())
        return res

    def unlink(self):
        tombstone_values = []
        try:
            access_recs = self.env['sh.powerbi.model.access'].sudo().search([
                ('model_name', '=', self._name),
                ('is_active', '=', True),
            ])
            if access_recs:
                for record in self:
                    for access in access_recs:
                        tombstone_values.append({
                            'name': '%s,%s' % (self._name, record.id),
                            'model_access_id': access.id,
                            'model_name': self._name,
                            'res_id': record.id,
                            'company_id': access.company_id.id,
                        })
        except Exception:
            _logger.exception("Power BI tombstone preparation failed for model %s", self._name)
            tombstone_values = []
        result = super().unlink()
        if tombstone_values:
            self.env['sh.powerbi.tombstone'].sudo().create(tombstone_values)
        return result

    def _sh_powerbi_queue_realtime(self):
        """Queue a realtime push job when a record is saved, if enabled on the config."""
        try:
            access_recs = self.env['sh.powerbi.model.access'].sudo().search([
                ('model_name', '=', self._name),
                ('is_active', '=', True),
                ('enable_realtime', '=', True),
                ('config_id.state', '=', 'authorized'),
            ])
            for access in access_recs:
                # Deduplicate: skip if a pending/processing job already exists
                already_queued = self.env['sh.powerbi.push.queue'].sudo().search_count([
                    ('push_config_id', '=', access.config_id.id),
                    ('model_access_id', '=', access.id),
                    ('state', 'in', ['draft', 'processing']),
                ])
                if not already_queued:
                    is_delta = (
                        access.enable_delta
                        and bool(access.powerbi_dataset_id)
                        and bool(access.last_push_write_date)
                    )
                    self.env['sh.powerbi.push.queue'].sudo().create({
                        'push_config_id': access.config_id.id,
                        'model_access_id': access.id,
                        'is_realtime': True,
                        'is_delta': is_delta,
                    })
        except Exception:
            # Never let realtime queueing crash the original write transaction
            _logger.exception("Power BI realtime queue error for model %s", self._name)

    @api.model
    @api.readonly
    def sh_powerbi_fetch_rows(self, fields=None, domain=None, offset=0, limit=1000, order='id asc'):
        """JSON-2 endpoint for model-driven Power BI row extraction."""
        _model_access, domain, fields = self._sh_powerbi_apply_access_rules(domain=domain, fields=fields)

        # Sudo is used on purpose so that this endpoint returns the exact same
        # rows and the same value types as sh_powerbi_search_read. Access is
        # enforced through the company scoped Power BI model access configuration
        # (allowed fields and domain filter) in _sh_powerbi_apply_access_rules.
        records = self.sudo().search(domain, offset=offset, limit=limit or False, order=order)
        if not records:
            return []

        rows = records.read(fields)
        return self._sh_powerbi_format_rows(rows, fields, _model_access)

    @api.model
    @api.readonly
    def sh_powerbi_count_rows(self, domain=None):
        """JSON-2 endpoint for row counts, used by paginated pull clients."""
        _model_access, domain, _fields = self._sh_powerbi_apply_access_rules(domain=domain, fields=['id'])
        return {
            'model': self._name,
            'count': self.search_count(domain),
        }
