import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Initialize Dash App
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "WellEcho - Advanced Reservoir Analytics"

# --- 1. Data Simulation (Physics Engine) ---

def generate_well_data():
    """Generates 365 days of synthetic data for 4 wells based on reservoir physics."""
    dates = [datetime(2025, 1, 1) + timedelta(days=i) for i in range(365)]
    all_data = []

    for well_name in ["T-01", "T-02", "T-03", "T-04"]:
        days = 365
        df = pd.DataFrame({'date': dates, 'well': well_name})
        
        # Default initialization (stochastic noise added later)
        df['oil_rate'] = 100.0  # Tonnes
        df['pressure'] = 250.0  # Bars
        df['water_cut'] = 5.0   # %
        df['gor'] = 100.0       # m3/m3
        
        if well_name == "T-01": # Cyclic Pressure Support
            # Pattern: 1 week flow (7 days), 2 weeks shut-in (14 days)
            cycle_len = 21
            for i in range(days):
                day_in_cycle = i % cycle_len
                
                if day_in_cycle < 7: # Flow Period
                    # Pressure declines rapidly, WC increases slightly
                    df.loc[i, 'oil_rate'] = 120 - (day_in_cycle * 2) # Declines 120 -> 108
                    df.loc[i, 'pressure'] = 200 - (day_in_cycle * 5) # Declines 200 -> 170
                    df.loc[i, 'water_cut'] = 10 + (day_in_cycle * 0.5) 
                else: # Shut-in Period
                    df.loc[i, 'oil_rate'] = 0
                    # Pressure builds up
                    buildup_days = day_in_cycle - 7
                    df.loc[i, 'pressure'] = 170 + (buildup_days * 5) # Rebuilds towards 240
                    df.loc[i, 'water_cut'] = 0 # No flow

        elif well_name == "T-02": # Post-Intervention Decline
            # 0-6 months (approx 180 days): Stable Plateau
            df.loc[:180, 'oil_rate'] = 150
            df.loc[:180, 'pressure'] = 280
            
            # Day 180: Workover Event (Simulated in data trends)
            
            # 6-12 months: Steep Exp Decline
            # Starting at 100T and declining
            for i in range(180, days):
                t = i - 180
                df.loc[i, 'oil_rate'] = 100 * np.exp(-0.005 * t)
                df.loc[i, 'pressure'] = 280 * np.exp(-0.002 * t)

        elif well_name == "T-03": # Water Breakthrough
            # Mid-year (Day 180) WC jumps 5% -> 65% over 10 days
            df['oil_rate'] = 200
            df['pressure'] = 300
            
            for i in range(days):
                if i < 180:
                    df.loc[i, 'water_cut'] = 5
                elif 180 <= i < 190:
                    # Transition period
                    progress = (i - 180) / 10
                    df.loc[i, 'water_cut'] = 5 + (60 * progress) # Linear ramp to 65
                    # Oil rate drops as water takes over
                    df.loc[i, 'oil_rate'] = 200 * (1 - progress * 0.6) 
                else:
                    df.loc[i, 'water_cut'] = 65
                    df.loc[i, 'oil_rate'] = 80 # Stabilized low oil rate

        elif well_name == "T-04": # High GOR
            # End of year (Day 330) GOR spike
            df['oil_rate'] = 180
            df['pressure'] = 260
            
            for i in range(days):
                if i < 330:
                    df.loc[i, 'gor'] = 100
                else:
                    # Spike 100 -> 800
                    days_into_spike = i - 330
                    df.loc[i, 'gor'] = 100 + (days_into_spike * 30) # Linear increase
                    if df.loc[i, 'gor'] > 800: df.loc[i, 'gor'] = 800
                    
                    # Gas breakout reduces liquid efficiency
                    df.loc[i, 'oil_rate'] = 180 - (days_into_spike * 2)

        # Add some sensor noise to all (except shut-ins)
        mask = df['oil_rate'] > 0
        df.loc[mask, 'oil_rate'] += np.random.normal(0, 2, size=mask.sum())
        df.loc[mask, 'pressure'] += np.random.normal(0, 1, size=mask.sum())
        
        all_data.append(df)

    return pd.concat(all_data, ignore_index=True)

# Generate Data on Startup
df_global = generate_well_data()

# --- User & Discipline Configuration ---
USERS = {
    'James Bishop': 'Geology',
    'Gaukhar': 'Petrophysics',
    'Medet': 'Petroleum',
    'Daniyar': 'Production',
    'Jambyl': 'Reservoir'
}

DISCIPLINE_COLORS = {
    'Geology': '#6f42c1',      # Purple
    'Reservoir': '#fd7e14',    # Orange
    'Petrophysics': '#20c997', # Teal
    'Production': '#198754',   # Green
    'Completion': '#0d6efd',   # Blue (Keeping for legacy/other)
    'Petroleum': '#dc3545'     # Red (Well Owner)
}

# --- Seeded History Data ---
SEEDED_EVENTS = [
    # T-01 (Cyclic)
    {"date": "2025-01-08", "well": "T-01", "type": "Shut-in", "discipline": "Reservoir", "author": "Jambyl", "action": "Shut-in", "status": "Closed", "depth": 0, "comment": "Shut-in well for pressure build-up.", "hashtags": "#BuildUp #PressureSupport"},
    {"date": "2025-01-22", "well": "T-01", "type": "Flowback", "discipline": "Production", "author": "Daniyar", "action": "Increase Choke", "status": "Open", "depth": 0, "comment": "Restarted production. Initial flow high, but expecting rapid decline.", "hashtags": "#Flowback"},
    
    # T-02 (Post-Intervention)
    {"date": "2025-04-01", "well": "T-02", "type": "Monitoring", "discipline": "Reservoir", "author": "Jambyl", "action": "None", "status": "Closed", "depth": 0, "comment": "Stable plateau maintained.", "hashtags": "#Plateau"},
    {"date": "2025-06-30", "well": "T-02", "type": "Workover", "discipline": "Production", "author": "Daniyar", "action": "Workover", "status": "Closed", "depth": 3500, "comment": "Workover completed: Serviced Sliding Sleeve.", "hashtags": "#Intervention #SlidingSleeve"},
    {"date": "2025-08-01", "well": "T-02", "type": "Analysis", "discipline": "Petroleum", "author": "Medet", "action": "Decrease Choke", "status": "Pending Approval", "depth": 0, "comment": "Observing unexpected decline post-workover. Potential skin damage.", "hashtags": "#DeclineAnalysis"},

    # T-03 (Water Breakthrough)
    {"date": "2025-06-10", "well": "T-03", "type": "Risk Alert", "discipline": "Geology", "author": "James Bishop", "action": "None", "status": "Open", "depth": 0, "comment": "Geology Note: Approaching suspected water-oil contact.", "hashtags": "#WOC #Risk"},
    {"date": "2025-07-01", "well": "T-03", "type": "Breakthrough", "discipline": "Petrophysics", "author": "Gaukhar", "action": "Decrease Choke", "status": "Pending Approval", "depth": 0, "comment": "Water breakthrough confirmed. Rates adjusting to high water cut.", "hashtags": "#Emergency"},

    # T-04 (High GOR)
    {"date": "2025-10-27", "well": "T-04", "type": "Geology Alert", "discipline": "Geology", "author": "James Bishop", "action": "None", "status": "Closed", "depth": 0, "comment": "Gas cap expansion noted in offset wells.", "hashtags": "#GasCap"},
    {"date": "2025-11-26", "well": "T-04", "type": "Choke Change", "discipline": "Production", "author": "Daniyar", "action": "Decrease Choke", "status": "Open", "depth": 0, "comment": "GOR spike detected. Implementing choke-back to protect reservoir energy.", "hashtags": "#HighGOR #ChokeOptimization"},
]

# --- Well Completion Configurations (Schematic Data) ---
WELL_COMPLETIONS = {
    "T-01": {
        "type": "Vertical",
        "packers": [3450],
        "ssds": [],
        "perfs": [(3500, 3550)], # Tuple: (Top, Bottom)
        "range": (3000, 4000) # Display Depth Range
    },
    "T-02": {
        "type": "Smart Completion",
        "packers": [3350, 3550], # Zonal Isolation for SSD
        "ssds": [3450],          # Controlled Zone
        "perfs": [(3450, 3500)],
        "range": (3000, 4000)
    },
    "T-03": {
        "type": "Vertical",
        "packers": [3600],
        "ssds": [],
        "perfs": [(3650, 3700)],
        "range": (3200, 4200)
    },
    "T-04": {
        "type": "Vertical",
        "packers": [4100],
        "ssds": [],
        "perfs": [(4150, 4200)],
        "range": (3800, 4800)
    }
}

# --- 2. UI Layout ---

# --- 2. UI Layout ---

# Theme Configuration
THEMES = {
    'light': {
        'background': '#f8f9fa',
        'content_bg': '#ffffff',
        'text': '#212529',
        'card_bg': '#ffffff',
        'border': '#dee2e6'
    },
    'dark': {
        'background': '#1e2130',
        'content_bg': '#1e2130',
        'text': '#e0e0e0',
        'card_bg': '#2a2d3e',
        'border': '#444'
    }
}

SIDEBAR_STYLE = {
    "position": "fixed", "top": 0, "left": 0, "bottom": 0, "width": "18rem",
    "padding": "2rem 1rem", 
    "zIndex": 1000, "overflowY": "auto",
    "transition": "all 0.5s",
}

CONTENT_STYLE = {
    "margin-left": "20rem", "margin-right": "2rem", "padding": "2rem 1rem",
    "transition": "all 0.5s",
}

sidebar = html.Div([
    html.H4("WellEcho", className="display-6", style={'color': '#002D62'}),
    html.Hr(),
    dbc.Input(id="well-search", placeholder="Search Wells...", type="text", className="mb-3"),
    html.P("Fleet Status", className="lead"),
    html.Div(id="well-status-list"), # Dynamic list with LEDs
    html.Hr(),
    html.Div([
        html.Small("T-01: Cyclic/Shut-in"), html.Br(),
        html.Small("T-02: Decline"), html.Br(),
        html.Small("T-03: Water Break"), html.Br(),
        html.Small("T-04: High GOR"),
    ], className="text-muted")
], style=SIDEBAR_STYLE, id="sidebar")

content = html.Div([
    # Header
    html.Div([
        # Row 1: Title & Controls
        html.Div([
            html.Div([
                dbc.Button("☰", id="btn-sidebar", color="light", className="me-2", style={'fontSize': '1.5rem', 'border': 'none', 'background': 'transparent'}),
                html.Div([
                    html.H2("Advanced Reservoir Analytics", style={'display': 'inline-block', 'marginBottom': '0px'}),
                    html.P("Real-time production monitoring and event registration", style={'color': '#888', 'marginBottom': '0px', 'fontSize': '0.9rem'}),
                ], style={'display': 'inline-block', 'verticalAlign': 'middle'})
            ], style={'display': 'flex', 'alignItems': 'center'}),
            
            # Dark Mode Toggle
            dbc.Switch(id="theme-toggle", label="Dark Mode", value=False, style={'display': 'inline-block'}),
            
        ], style={'padding': '10px 0px', 'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between', 'borderBottom': '1px solid #dee2e6', 'marginBottom': '20px'}),

        # Row 2: KPI Ribbon (Dynamic Content)
        dbc.Row(id="kpi-ribbon", className="mb-4"),
    ], id="header-container"),

    # Main Row: Chart + Range Slider
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Production Trends"),
                dbc.CardBody([
                    dcc.Graph(id='main-chart', style={'height': '600px'}),
                    html.Div([
                        html.Label("Filter Date Range (Days 0 - 365):"),
                        dcc.RangeSlider(
                            id='date-slider',
                            min=0,
                            max=364,
                            value=[0, 364],
                            marks={0: 'Jan', 90: 'Apr', 180: 'Jul', 270: 'Oct', 364: 'Dec'},
                            tooltip={"placement": "bottom", "always_visible": True}
                        )
                    ], style={'padding': '20px'})
                ])
            ], id="chart-card")
        ], width=12),
    ], className="mb-4"),

    # Second Row: Input Form & Wellbore
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Register New Well Event/Intervention", className="bg-warning text-dark"),
                dbc.CardBody([
                     # Decision Module Row (User + Action + Status)
                    dbc.Row([
                        dbc.Col([
                            html.Label("Select User (Author)"),
                            dcc.Dropdown(
                                id='event-user',
                                options=[{'label': f"{name} ({disc})", 'value': name} for name, disc in USERS.items()],
                                value='Medet',
                                clearable=False
                            ),
                        ], width=4),
                        dbc.Col([
                            html.Label("Action Recommended"),
                            dcc.Dropdown(
                                id='event-action',
                                options=['None', 'Increase Choke', 'Decrease Choke', 'Workover', 'Acidize', 'Shut-in'],
                                value='None'
                            ),
                        ], width=4),
                        dbc.Col([
                            html.Label("Status"),
                            dcc.Dropdown(
                                id='event-status',
                                options=['Open', 'Closed', 'Pending Approval'],
                                value='Open'
                            ),
                        ], width=4),
                    ], className="mb-3"),
                    
                    # Input Fields Row
                    dbc.Row([
                        dbc.Col([
                            html.Label("Date"),
                            dcc.DatePickerSingle(
                                id='event-date',
                                date=datetime(2025, 6, 15),
                                display_format='YYYY-MM-DD',
                                style={'width': '100%'}
                            ),
                        ], width=3),
                        dbc.Col([
                            html.Label("Event Type"),
                            dcc.Dropdown(
                                id='event-type',
                                options=['Workover', 'Stimulation', 'Choke Change', 'Shut-in', 'Monitoring', 'Risk Alert'],
                                value='Workover',
                            ),
                        ], width=3),
                        dbc.Col([
                            html.Label("Depth (m)"),
                            dbc.Input(id='event-depth', type='number', placeholder='3500'),
                        ], width=3),
                        dbc.Col([
                            html.Label("Hashtags"),
                            dbc.Input(id='event-hashtag', placeholder='#tag'),
                        ], width=3),
                    ], className="mb-2"),
                    
                    dbc.Row([
                        dbc.Col([
                            html.Label("Comment"),
                            dbc.Input(id='event-comment', placeholder='Details...', type="text"),
                        ], width=9),
                        dbc.Col([
                            html.Label("Action"),
                            dbc.Button("Submit", id='btn-submit', color='primary', className="w-100"),
                        ], width=3),
                    ], align="end"),
                    html.Div(id='form-feedback', className="mt-2 text-danger")
                ])
            ], id="form-card", className="mb-4", style={"height": "100%"})
        ], width=8),

        # Wellbore Mini-Map
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Wellbore Diagram"),
                dbc.CardBody(html.Div(id='wellbore-diagram', style={'height': '350px', 'position': 'relative'}))
            ], id="wellbore-card", style={"height": "100%"})
        ], width=4),
    ]),

    # Third Row: History Table
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    "Well History Table",
                    dbc.Button("Download Structured Data for ML", id="btn-download", color="success", size="sm", className="float-end")
                ]),
                dbc.CardBody(html.Div(id='history-table-container'))
            ], id="table-card")
        ], width=12),
    ]),

    # Footer
    html.Div([
        html.Hr(),
        html.P([
            "Connected to Azure Synapse | ",
            html.Span(f"Last Sync: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | ", id='sync-time'),
            "200/200 Wells Online"
        ], className="text-muted text-center small")
    ])
], style=CONTENT_STYLE, id="page-content")

app.layout = html.Div([
    dcc.Store(id='event-store', data=SEEDED_EVENTS),
    dcc.Store(id='theme-store', data='light'),
    dcc.Store(id='selected-well-store', data='T-01'), # Replaces simplified dropdown value
    dcc.Download(id="download-dataframe-csv"),
    html.Div([sidebar, content], id='main-container', style={'backgroundColor': '#f8f9fa', 'minHeight': '100vh'})
])

# --- 3. Callbacks ---

@app.callback(
    [Output("sidebar", "style"),
     Output("page-content", "style"),
     Output("main-container", "style"),
     Output("chart-card", "style"),
     Output("form-card", "style"),
     Output("table-card", "style"),
     Output("sidebar", "className")],
    [Input("btn-sidebar", "n_clicks"),
     Input("theme-toggle", "value")],
    [State("sidebar", "style"),
     State("page-content", "style")]
)
def update_layout_and_theme(n_clicks, dark_mode, sidebar_style, content_style):
    # Determine Theme
    theme = THEMES['dark'] if dark_mode else THEMES['light']
    
    # Update Styles
    main_style = {'backgroundColor': theme['background'], 'minHeight': '100vh', 'color': theme['text']}
    card_style = {'backgroundColor': theme['card_bg'], 'border': f"1px solid {theme['border']}", 'color': theme['text']}
    
    sidebar_style['backgroundColor'] = theme['background'] if dark_mode else '#f8f9fa'
    sidebar_style['color'] = theme['text']
    sidebar_style['borderRight'] = f"1px solid {theme['border']}"
    
    # Toggle Logic
    if n_clicks and n_clicks % 2 == 1:
        sidebar_style["width"] = "0rem"
        sidebar_style["overflow"] = "hidden"
        sidebar_style["padding"] = "0rem"
        content_style["margin-left"] = "2rem"
    else:
        sidebar_style["width"] = "18rem"
        sidebar_style["overflow"] = "auto"
        sidebar_style["padding"] = "2rem 1rem"
        content_style["margin-left"] = "20rem"

    return sidebar_style, content_style, main_style, card_style, card_style, card_style, "bg-dark text-light" if dark_mode else "bg-light text-dark"

@app.callback(
    Output("well-status-list", "children"),
    [Input("well-search", "value"),
     Input("selected-well-store", "data")]
)
def update_well_list(search_term, selected_well):
    wells = [
        {"name": "T-01", "status": "warning"}, # Yellow
        {"name": "T-02", "status": "success"}, # Green
        {"name": "T-03", "status": "danger"},  # Red
        {"name": "T-04", "status": "danger"}   # Red
    ]
    
    if search_term:
        wells = [w for w in wells if search_term.lower() in w['name'].lower()]
        
    items = []
    for w in wells:
        is_active = (w['name'] == selected_well)
        
        # LED Light
        led_color = "#ffc107" if w['status'] == "warning" else "#198754" if w['status'] == "success" else "#dc3545"
        led = html.Span(style={
            "height": "12px", "width": "12px", "backgroundColor": led_color,
            "borderRadius": "50%", "display": "inline-block", "marginRight": "10px",
            "boxShadow": f"0 0 5px {led_color}"
        })
        
        item = dbc.ListGroupItem(
            [led, w['name']],
            id={"type": "well-item", "index": w["name"]},
            action=True,
            active=is_active,
            color="dark" if selected_well == w['name'] else "light", # Highlight active
            style={'cursor': 'pointer', 'border': 'none', 'backgroundColor': 'transparent'} 
        )
        items.append(item)
    
    return dbc.ListGroup(items, flush=True)

@app.callback(
    Output("selected-well-store", "data"),
    [Input({"type": "well-item", "index": dash.ALL}, "n_clicks")],
    [State({"type": "well-item", "index": dash.ALL}, "id")]
)
def set_selected_well(n_clicks, ids):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update
    
    # Find which button was clicked
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    import json
    button_id = json.loads(button_id)
    return button_id['index']

@app.callback(
    Output("download-dataframe-csv", "data"),
    Input("btn-download", "n_clicks"),
    State("event-store", "data"),
    prevent_initial_call=True,
)
def download_csv(n_clicks, events):
    df = pd.DataFrame(events)
    return dcc.send_data_frame(df.to_csv, "well_history_data.csv")

@app.callback(
    [Output('event-store', 'data'),
     Output('form-feedback', 'children')],
    [Input('btn-submit', 'n_clicks')],
    [State('selected-well-store', 'data'),
     State('event-date', 'date'),
     State('event-type', 'value'),
     State('event-user', 'value'),
     State('event-action', 'value'),
     State('event-status', 'value'),
     State('event-depth', 'value'),
     State('event-comment', 'value'),
     State('event-hashtag', 'value'),
     State('event-store', 'data')]
)
def register_event(n_clicks, well, date, w_type, user, action, status, depth, comment, hashtags, current_data):
    if not n_clicks:
        return current_data, ""
    
    # Validation and convert depth to float
    try:
        if depth:
            depth = float(depth)
        else:
            depth = 0 # Default if not provided or N/A
    except (ValueError, TypeError):
        return current_data, "❌ Error: Invalid depth format."

    if not comment:
        return current_data, "❌ Error: Comment is required."

    # Lookup Discipline based on User
    discipline = USERS.get(user, 'Unknown')

    new_event = {
        'date': date,
        'well': well,
        'type': w_type,
        'discipline': discipline,
        'author': user,
        'action': action,
        'status': status,
        'depth': depth,
        'comment': comment,
        'hashtags': hashtags
    }
    
    # Prepend to list
    current_data.insert(0, new_event)
    return current_data, ""

@app.callback(
    Output('history-table-container', 'children'),
    [Input('event-store', 'data'),
     Input('selected-well-store', 'data'),
     Input('theme-toggle', 'value')]
)
def update_feed(events, selected_well, dark_mode):
    # Filter for selected well
    well_events = [e for e in events if e['well'] == selected_well]
    # Sort by date descending
    well_events.sort(key=lambda x: x['date'], reverse=True)
    
    if not well_events:
        return html.P("No events registered for this well.", className="text-muted text-center mt-4")

    # Theme
    text_color = "#e0e0e0" if dark_mode else "#212529"
    card_bg = "#2a2d3e" if dark_mode else "#ffffff"
    border = "#444" if dark_mode else "#dee2e6"
    sub_text = "#adb5bd" if dark_mode else "#6c757d"

    feed_items = []
    for event in well_events:
        disc = event.get('discipline', 'Unknown')
        author = event.get('author', 'Unknown')
        color = DISCIPLINE_COLORS.get(disc, '#6c757d')
        
        # Initials for Avatar
        initials = "".join([n[0] for n in author.split()])[:2]
        
        # Status Badge Logic
        status = event.get('status', 'Open')
        status_color = "success" if status == "Closed" else "warning" if status == "Pending Approval" else "danger"
        
        card = dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    # Avatar
                    dbc.Col(html.Div(initials, style={
                        "width": "40px", "height": "40px", "borderRadius": "50%", 
                        "backgroundColor": color, "color": "white",
                        "display": "flex", "alignItems": "center", "justifyContent": "center",
                        "fontWeight": "bold"
                    }), width="auto"),
                    
                    # Author & Meta
                    dbc.Col([
                        html.H6(author, className="mb-0", style={"color": text_color}),
                        html.Small(f"{disc} • {event['date'][:10]}", style={"color": sub_text})
                    ]),
                    
                    # Status Pill
                    dbc.Col(
                        dbc.Badge(status, color=status_color, pill=True),
                        width="auto", className="text-end"
                    )
                ], className="mb-2 align-items-center"),
                
                # Content
                html.P(event['comment'], className="card-text", style={"color": text_color, "fontSize": "1.05rem"}),
                
                # Tags & Details
                html.Div([
                    dbc.Badge(event['type'], color="info", className="me-2", text_color="white"),
                    html.Span(f"Action: {event.get('action', '-')}", className="small me-3", style={"color": sub_text}),
                    html.Span(f"Depth: {event.get('depth', 0)}m", className="small me-3", style={"color": sub_text}),
                    html.Span(event['hashtags'], className="small text-primary")
                ], className="mb-3"),
                
                # Footer Actions
                html.Div([
                    dbc.Button([html.Span("👍"), " Like"], size="sm", color="link", className="text-decoration-none ps-0", style={"color": sub_text}),
                    dbc.Button([html.Span("↩"), " Reply"], size="sm", color="link", className="text-decoration-none", style={"color": sub_text}),
                    html.A("📎 View Tech Attach", href="#", className="small text-decoration-none ms-auto", style={"color": "#0d6efd"})
                ], className="d-flex border-top pt-2")
            ])
        ], className="mb-3", style={"backgroundColor": card_bg, "border": f"1px solid {border}"})
        
        feed_items.append(card)
    
    return html.Div(feed_items)

@app.callback(
    Output('main-chart', 'figure'),
    [Input('selected-well-store', 'data'),
     Input('event-store', 'data'),
     Input('date-slider', 'value'),
     Input('theme-toggle', 'value')]
)
def update_chart(well, events, date_range, dark_mode):
    # 1. Slice by well
    dff = df_global[df_global['well'] == well].copy()
    
    # 2. Slice by date slider (index-based)
    start_idx, end_idx = date_range
    dff = dff.iloc[start_idx:end_idx+1]
    
    # Check if dataframe is empty after slicing
    if dff.empty:
        # Return empty figure with message
        theme = THEMES['dark'] if dark_mode else THEMES['light']
        fig = go.Figure()
        fig.update_layout(
            title=f"Production Overview: {well} - No Data Available",
            title_font_color=theme['text'],
            plot_bgcolor=theme['card_bg'],
            paper_bgcolor=theme['card_bg'],
            template="plotly_dark" if dark_mode else "plotly_white"
        )
        return fig
    
    # Theme settings
    theme = THEMES['dark'] if dark_mode else THEMES['light']
    grid_color = "#555" if dark_mode else "#eee"

    fig = go.Figure()

    # Left Axis: Oil Rate
    fig.add_trace(go.Bar(
        x=dff['date'], y=dff['oil_rate'],
        name='Oil Rate (Tonnes)',
        marker_color='#2c3e50' if not dark_mode else '#4a6fa5', opacity=0.8,
        yaxis='y'
    ))

    # Right Axis: Pressure
    fig.add_trace(go.Scatter(
        x=dff['date'], y=dff['pressure'],
        name='Pressure (Bars)',
        line=dict(color='#e74c3c', width=2),
        yaxis='y2'
    ))

    # Right Axis: Water Cut
    fig.add_trace(go.Scatter(
        x=dff['date'], y=dff['water_cut'],
        name='Water Cut (%)',
        line=dict(color='#3498db', width=2, dash='dash'),
        yaxis='y2'
    ))
    
    # Right Axis: GOR
    fig.add_trace(go.Scatter(
        x=dff['date'], y=dff['gor'],
        name='GOR (m3/m3)',
        line=dict(color='#f39c12', width=2, dash='dot'),
        yaxis='y2'
    ))

    # Add Vertical Lines & Badges for Events
    well_events = [e for e in events if e['well'] == well]
    
    # Avoid overlapping annotations by staggering y-position
    y_positions = [1.02, 1.08, 1.14] 
    
    for i, e in enumerate(well_events):
        event_date = pd.to_datetime(e['date'])
        
        # Only show event if date is within view range
        if dff['date'].min() <= event_date <= dff['date'].max():
            # Use datetime object directly for Plotly
            x_pos = event_date
            
            # 1. Dashed Line
            fig.add_vline(
                x=x_pos, 
                line_width=1, line_dash="dash", line_color=theme['text'], opacity=0.5
            )
            
            # 2. Author Badge Annotation
            disc = e.get('discipline', 'Unknown')
            color = DISCIPLINE_COLORS.get(disc, '#6c757d')
            
            # Stagger text to avoid overlap
            y_pos = y_positions[i % len(y_positions)]
            
            fig.add_annotation(
                x=x_pos, y=y_pos, yref='paper',
                text=f"<b>{e['type']}</b><br><span style='font-size:10px'>{e.get('author', '')}</span>",
                showarrow=False,
                bgcolor=color,
                bordercolor=color,
                borderwidth=1,
                borderpad=4,
                font=dict(color='white', size=11),
                align="center"
            )
    
    fig.update_layout(
        title=f"Production Overview: {well}",
        title_font_color=theme['text'],
        plot_bgcolor=theme['card_bg'],
        paper_bgcolor=theme['card_bg'],
        xaxis=dict(title="Date", color=theme['text'], gridcolor=grid_color),
        yaxis=dict(title="Oil Rate (Tonnes)", side="left", color=theme['text'], gridcolor=grid_color),
        yaxis2=dict(
            title="Pressure (Bars) / WC / GOR", 
            side="right",
            overlaying="y",
            showgrid=False,
            color=theme['text']
        ),
        legend=dict(orientation="h", y=-0.15, x=0, font=dict(color=theme['text'])),
        margin=dict(l=50, r=50, t=100, b=50), # Increased top margin for annotations
        template="plotly_dark" if dark_mode else "plotly_white"
    )

    return fig

@app.callback(
    Output("kpi-ribbon", "children"),
    [Input("selected-well-store", "data"),
     Input("event-store", "data"),
     Input("theme-toggle", "value")]
)
def update_kpi_ribbon(well, events, dark_mode):
    # 1. Get Well Data
    dff = df_global[df_global['well'] == well].copy()
    
    # Check if dataframe has data
    if dff.empty:
        # Return empty KPI ribbon with default message
        text_color = "#e0e0e0" if dark_mode else "#212529"
        card_bg = "#2a2d3e" if dark_mode else "#ffffff"
        border = "#444" if dark_mode else "#dee2e6"
        card_style = {"backgroundColor": card_bg, "border": f"1px solid {border}", "color": text_color}
        
        return [
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("No Data Available", className="card-subtitle mb-2 text-muted"),
                    html.H3("N/A", style={"color": text_color, "fontWeight": "bold"}),
                ])
            ], style=card_style), width=12),
        ]
    
    last_row = dff.iloc[-1]
    last_week = dff.iloc[-7] if len(dff) > 7 else dff.iloc[0]
    
    # 2. Logic
    is_producing = last_row['oil_rate'] > 0
    status_text = "ACTIVE" if is_producing else "SHUT-IN"
    status_color = "#198754" if is_producing else "#dc3545" # Green / Red
    
    current_oil = last_row['oil_rate']
    current_pressure = last_row['pressure']
    pressure_trend = "▲" if current_pressure > last_week['pressure'] else "▼"
    
    # 3. Task Count
    well_events = [e for e in events if e['well'] == well]
    pending_tasks = sum(1 for e in well_events if e.get('status') in ['Open', 'Pending Approval'])
    
    # Theme
    text_color = "#e0e0e0" if dark_mode else "#212529"
    card_bg = "#2a2d3e" if dark_mode else "#ffffff"
    border = "#444" if dark_mode else "#dee2e6"

    card_style = {"backgroundColor": card_bg, "border": f"1px solid {border}", "color": text_color}
    
    # Sparkline (Simplified)
    sparkline = go.Figure(go.Scatter(y=dff['oil_rate'].tail(30), mode='lines', line=dict(color='#20c997', width=2)))
    sparkline.update_layout(
        margin=dict(l=0, r=0, t=0, b=0), height=40, 
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
    )

    return [
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H6("Well Status", className="card-subtitle mb-2 text-muted"),
                html.H3(status_text, style={"color": status_color, "fontWeight": "bold"}),
                html.Small(f"Target: {'150t' if well == 'T-02' else '120t'}")
            ])
        ], style=card_style), width=3),
        
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H6("24h Production", className="card-subtitle mb-2 text-muted"),
                html.H3(f"{current_oil:.1f} t"),
                dcc.Graph(figure=sparkline, config={'displayModeBar': False}, style={'height': '40px'})
            ])
        ], style=card_style), width=3),
        
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H6("Res. Pressure", className="card-subtitle mb-2 text-muted"),
                html.H3(f"{int(current_pressure)} Bar"),
                html.Small(f"{pressure_trend} vs last week", className="text-muted")
            ])
        ], style=card_style), width=3),
        
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H6("Pending Tasks", className="card-subtitle mb-2 text-muted"),
                html.H3(f"{pending_tasks}", className="text-warning"),
                html.Small("Requires Action")
            ])
        ], style=card_style), width=3),
    ]

def draw_completion_hardware(well_name, dark_mode):
    """
    Generates the Dash components for the wellbore schematic based on the configuration.
    Iterates through depths to render Packers, SSDs, and Perforations scaling to the view range.
    """
    config = WELL_COMPLETIONS.get(well_name, WELL_COMPLETIONS["T-01"])
    min_d, max_d = config['range']
    total_depth = max_d - min_d
    
    # Theme Colors
    casing_color = "#6c757d" if not dark_mode else "#6c757d"
    tubing_color = "#212529" if not dark_mode else "#adb5bd"
    packer_color = "black"  # User requested solid black
    text_color = "#212529" if not dark_mode else "#e0e0e0"

    def to_pct(depth):
        """Converts depth to percentage relative to the container height."""
        # Clamp to 0-100 for safety, though things outside range just won't show or will be clipped
        return (depth - min_d) / total_depth * 100

    elements = []
    
    # 0. Background / Container Context (Optional, provided by parent card)
    
    # 1. Base Architecture (Casing & Tubing)
    # Casing Lines (Left and Right borders)
    elements.append(html.Div(style={
        "position": "absolute", "top": "0", "bottom": "0", "left": "25%", "right": "25%",
        "borderLeft": f"5px solid {casing_color}", "borderRight": f"5px solid {casing_color}",
        "zIndex": 10
    }))
    
    # Tubing (Central Pipe)
    elements.append(html.Div(style={
        "position": "absolute", "top": "0", "bottom": "0", "left": "46%", "right": "46%",
        "backgroundColor": tubing_color,
        "zIndex": 20
    }))
    
    # 2. Iterate and Draw Hardware
    
    # Packers: "Solid black blocks... wedged between tubing and casing"
    for d in config['packers']:
        pct = to_pct(d)
        if 0 <= pct <= 100:
            # Left Packer Block
            elements.append(html.Div(style={
                "position": "absolute", "top": f"{pct}%", "height": "15px",
                "left": "25%", "width": "21%", # 25% to 46% = 21% gap
                "backgroundColor": packer_color, "zIndex": 15
            }))
            # Right Packer Block
            elements.append(html.Div(style={
                "position": "absolute", "top": f"{pct}%", "height": "15px",
                "right": "25%", "width": "21%", 
                "backgroundColor": packer_color, "zIndex": 15
            }))
            # Label
            elements.append(html.Div(f"Pkr @ {d}m", style={
                "position": "absolute", "top": f"{pct}%", "right": "5px", 
                "fontSize": "10px", "color": text_color, "marginTop": "-5px"
            }))

    # Sliding Sleeves (SSD): "Small hollow rectangular gap"
    for d in config['ssds']:
        pct = to_pct(d)
        if 0 <= pct <= 100:
            # SSD Window
            elements.append(html.Div(title=f"SSD @ {d}m", style={
                "position": "absolute", "top": f"{pct}%", "height": "25px",
                "left": "45%", "right": "45%", # Slightly wider than tubing to stand out
                "backgroundColor": "#fff" if not dark_mode else "#333", 
                "border": "2px solid #0d6efd", # Blue highlight
                "zIndex": 30
            }))
            # Label
            elements.append(html.Div(f"SSD @ {d}m", style={
                "position": "absolute", "top": f"{pct}%", "left": "10px", 
                "fontSize": "10px", "color": "#0d6efd", "marginTop": "0px", "fontWeight": "bold"
            }))

    # Perforations: "Starburst patterns that extend from casing into formation"
    for top, bot in config['perfs']:
        top_pct = to_pct(top)
        bot_pct = to_pct(bot)
        height = max(bot_pct - top_pct, 2) # Ensure visible height
        
        if top_pct < 100 and bot_pct > 0:
            # We draw a container outside the casing with a visualization pattern
            
            # Left Perf Zone
            elements.append(html.Div(style={
                "position": "absolute", "top": f"{top_pct}%", "height": f"{height}%",
                "left": "15%", "width": "10%", 
                "backgroundImage": "linear-gradient(90deg, transparent 50%, #dc3545 50%)", # Simple dashes
                "backgroundSize": "10px 4px",
                "zIndex": 5
            }))
            
            # Right Perf Zone
            elements.append(html.Div(style={
                "position": "absolute", "top": f"{top_pct}%", "height": f"{height}%",
                "right": "15%", "width": "10%",
                "backgroundImage": "linear-gradient(90deg, #dc3545 50%, transparent 50%)",
                "backgroundSize": "10px 4px",
                "zIndex": 5
            }))
            
            # Depth Label
            elements.append(html.Div(f"Perfs: {top}-{bot}m", style={
                "position": "absolute", "top": f"{top_pct}%", "right": "5px",
                "fontSize": "9px", "color": "#dc3545", "transform": "translateY(15px)"
            }))

    # Legend/Title Overlay
    elements.append(html.Div([
        html.Strong(well_name, style={"fontSize": "1.2rem"}),
        html.Br(),
        html.Small(f"View: {min_d}-{max_d}m", className="text-muted")
    ], style={"position": "absolute", "top": "10px", "left": "10px", "color": text_color}))

    return elements

@app.callback(
    Output("wellbore-diagram", "children"),
    [Input("selected-well-store", "data"),
     Input("theme-toggle", "value")]
)
def update_wellbore(well, dark_mode):
    return draw_completion_hardware(well, dark_mode)

if __name__ == '__main__':
    app.run_server(debug=True, port=8051)
