# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from odoo import http
from odoo.http import request


class SHPowerBIEmbedController(http.Controller):

    def _render_embed_html(self, report_name, embed_url, embed_token, is_preview=False, embed_type='report'):
        badge_text = "Preview Mode" if is_preview else "Live &amp; Syncing"
        badge_color = "#3498db" if is_preview else "#2ecc71"
        pulse_color = "#2980b9" if is_preview else "#27ae60"
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report_name}</title>
    <script src="https://cdn.jsdelivr.net/npm/powerbi-client@2.22.2/dist/powerbi.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f4f6f9;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        .pbi-header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            color: white;
            padding: 12px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            flex-shrink: 0;
        }}
        .pbi-header .title {{
            font-size: 16px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .pbi-header .title svg {{ width: 24px; height: 24px; }}
        .pbi-header .actions {{ display: flex; gap: 10px; align-items: center; }}
        .btn {{
            padding: 6px 14px;
            border-radius: 6px;
            border: none;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s;
        }}
        .btn-primary {{ background: #f5a623; color: #1a1a2e; }}
        .btn-primary:hover {{ background: #e09510; transform: translateY(-1px); }}
        .btn-outline {{
            background: transparent;
            color: white;
            border: 1px solid rgba(255,255,255,0.4);
        }}
        .btn-outline:hover {{ background: rgba(255,255,255,0.1); }}
        .status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 5px;
            background: rgba(255,255,255, 0.1);
            border: 1px solid {badge_color};
            color: {badge_color};
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }}
        .status-badge .dot {{
            width: 7px; height: 7px;
            background: {pulse_color};
            border-radius: 50%;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.6; transform: scale(0.85); }}
        }}
        .pbi-embed-container {{
            flex: 1;
            position: relative;
            overflow: hidden;
        }}
        #reportContainer {{
            width: 100%;
            height: 100%;
            border: none;
        }}
        .loading-overlay {{
            position: absolute;
            inset: 0;
            background: white;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 16px;
            z-index: 10;
        }}
        .spinner {{
            width: 48px; height: 48px;
            border: 4px solid #f0f0f0;
            border-top-color: #f5a623;
            border-radius: 50%;
            animation: spin 0.9s linear infinite;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        .loading-text {{ color: #666; font-size: 14px; }}
        .error-overlay {{
            position: absolute;
            inset: 0;
            background: white;
            display: none;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 12px;
            z-index: 10;
        }}
        .error-icon {{ font-size: 48px; }}
        .error-msg {{ color: #e74c3c; font-size: 15px; text-align: center; max-width: 400px; }}
        .sync-info {{
            font-size: 12px;
            color: rgba(255,255,255,0.6);
        }}
    </style>
</head>
<body>
    <div class="pbi-header">
        <div class="title">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="2" y="12" width="4" height="10" rx="1" fill="#f5a623"/>
                <rect x="8" y="7" width="4" height="15" rx="1" fill="#f5a623" opacity="0.8"/>
                <rect x="14" y="3" width="4" height="19" rx="1" fill="#f5a623" opacity="0.6"/>
                <path d="M20 2L22 4L20 6" stroke="#f5a623" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            {report_name}
        </div>
        <div class="actions">
            <span class="status-badge">
                <span class="dot"></span>
                {badge_text}
            </span>
            <a href="https://app.powerbi.com" target="_blank" class="btn btn-outline">
                &#x2197; Open in Power BI
            </a>
            <button class="btn btn-primary" onclick="refreshReport()">&#x21bb; Refresh</button>
        </div>
    </div>
    <div class="pbi-embed-container">
        <div class="loading-overlay" id="loadingOverlay">
            <div class="spinner"></div>
            <div class="loading-text">Loading Power BI Report...</div>
        </div>
        <div class="error-overlay" id="errorOverlay">
            <div class="error-icon">&#x26A0;</div>
            <div class="error-msg" id="errorMsg">Failed to load the report.</div>
            <button class="btn btn-primary" onclick="location.reload()">Retry</button>
        </div>
        <div id="reportContainer"></div>
    </div>

    <script>
        const models_pbi = window['powerbi-client'].models;
        const EMBED_URL = '{embed_url}';
        const EMBED_TOKEN = '{embed_token}';
        let embeddedReport = null;

        function showError(msg) {{
            document.getElementById('loadingOverlay').style.display = 'none';
            const overlay = document.getElementById('errorOverlay');
            overlay.style.display = 'flex';
            document.getElementById('errorMsg').textContent = msg;
        }}

        function embedReport() {{
            if (!EMBED_URL || !EMBED_TOKEN) {{
                showError('Embed URL or Token is missing. Please generate an embed token in Odoo first.');
                return;
            }}
            const config = {{
                type: '{embed_type}',
                tokenType: models_pbi.TokenType.Embed,
                accessToken: EMBED_TOKEN,
                embedUrl: EMBED_URL,
                settings: {{
                    panes: {{
                        filters: {{ expanded: false, visible: true }},
                        pageNavigation: {{ visible: true }},
                    }},
                    background: models_pbi.BackgroundType.Default,
                }},
            }};
            const container = document.getElementById('reportContainer');
            embeddedReport = window.powerbi.embed(container, config);
            embeddedReport.on('loaded', function () {{
                document.getElementById('loadingOverlay').style.display = 'none';
            }});
            embeddedReport.on('error', function (event) {{
                showError('Power BI error: ' + (event.detail && event.detail.message ? event.detail.message : 'Unknown error'));
            }});
        }}

        function refreshReport() {{
            if (embeddedReport) {{
                embeddedReport.refresh().catch(function(err) {{
                    console.warn('Refresh failed:', err);
                }});
            }}
        }}

        window.addEventListener('DOMContentLoaded', embedReport);
    </script>
</body>
</html>"""
        return html

    @http.route('/sh_power_bi/embed/<int:report_id>', auth='user', type='http', csrf=False)
    def embed_report(self, report_id, **kwargs):
        """Serve the embedded Power BI report page with the JS SDK."""
        record = request.env['sh.powerbi.embedded.report'].browse(report_id)
        if not record.exists():
            return request.not_found()

        embed_url = record.embed_url or ''
        embed_token = record.embed_token or ''
        report_name = record.name or 'Power BI Report'

        return self._render_embed_html(report_name, embed_url, embed_token)
        
    @http.route('/sh_power_bi/embed_preview/<int:asset_id>', auth='user', type='http', csrf=False)
    def embed_preview(self, asset_id, **kwargs):
        """Serve the preview for a report or dashboard asset."""
        asset_type = kwargs.get('type', 'report')
        if asset_type == 'dashboard':
            record = request.env['sh.powerbi.dashboard.asset'].browse(asset_id)
            report_name = record.name or 'Power BI Dashboard Preview'
        else:
            record = request.env['sh.powerbi.report'].browse(asset_id)
            report_name = record.name or 'Power BI Report Preview'

        if not record.exists():
            return request.not_found()

        embed_url = record.embed_url or ''
        embed_token = record.embed_token or ''

        return self._render_embed_html(report_name, embed_url, embed_token, is_preview=True, embed_type=asset_type)
