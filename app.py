# -*- coding: utf-8 -*-
# The first section creates datasets and figures to be used by the tabs.
# The second section defines the layout. 
# The third section consists of the callbacks that make the app interactive.

import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_table
import plotly.express as px
import pandas as pd
import numpy as np
import yaml
import psycopg2
from sqlalchemy import create_engine
from psycopg2 import OperationalError, sql
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go
import networkx as nx

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

server = app.server

# ------------- Set up connection to DB ------------------
with open('/path/to/gutensearch/dbconfig.yml', 'r') as ymlfile: 
    cfg = yaml.load(ymlfile, Loader=yaml.SafeLoader)

engine = create_engine(cfg['Postgres']['constring'])

# ------------- Get data into Pandas dataframes ----------
supported_languages = pd.DataFrame(engine.execute("""select distinct language from gutenberg.all_data where lower(language) in (SELECT cfgname FROM pg_ts_config) order by language asc;"""))
supported_languages.columns =['language']
authors = pd.DataFrame(engine.execute("""select distinct author from gutenberg.all_data where lower(language) in (SELECT cfgname FROM pg_ts_config) order by author asc;"""))
authors.columns =['author']
unsupported_languages = pd.DataFrame(engine.execute("""with languages as (select distinct language from gutenberg.all_data where lower(language) not in (SELECT cfgname FROM pg_ts_config) order by language asc) select string_agg(language, ', ') as languages from languages;"""))
unsupported_languages.columns =['languages']

mentioned_authors = pd.DataFrame(engine.execute("""select mentioned_author, mentioned_by, books_mentioned_in from gutenberg.mentioned_authors;"""))
mentioned_authors.columns = ['mentioned_author', 'mentioned_by', 'books_mentioned_in']
mentioned_authors_graph = nx.from_pandas_edgelist(mentioned_authors, "mentioned_author", "mentioned_by", ["books_mentioned_in"])

book_length = pd.DataFrame(engine.execute("""select num, case when language in ('English', 'French', 'German') then language else 'Other' end as language, length from gutenberg.all_data where length <> 0;"""))
book_length.columns = ['num', 'language', 'length']

book_length['log_length'] = np.log10(book_length['length']) 
book_length[' index'] = book_length['num']

# ------------- Create figures for Statistics tab --------
fig1 = px.histogram(book_length, x="log_length", color="language", facet_col="language", category_orders={"language": ["English", "French", "German", "Other"]}, labels={
                     "log_length": "log(Total characters in book)",
                     "count": "Count of books with this length",
                     "language": "Language"
                 })

# Books per (supported) language
books_per_language = pd.DataFrame(engine.execute("""select language, count(*) as books, case when lower(language) in (SELECT cfgname FROM pg_ts_config) then 'Yes' else 'No' end as supported from gutenberg.all_data where language is not null group by language order by books desc, supported desc, language asc;"""))
books_per_language.columns = ['language', 'books', 'supported']

fig2 = px.bar(books_per_language, x='language', y='books', color='supported', log_y=True, hover_name='books', labels={
                     "language": "Language",
                     "books": "Number of books",
                     "supported": "Language is supported by PostgreSQL Full Text Search"
                 })
fig2.update_layout(legend=dict(
    orientation="h",
    yanchor="bottom",
    y=1.02,
    xanchor="right",
    x=1
))

trace1 = go.Bar(x=books_per_language[books_per_language.supported == 'Yes']['language'], y=books_per_language[books_per_language.supported == 'Yes']['books'], name='Supported languages')
trace2 = go.Bar(x=books_per_language[books_per_language.supported == 'No']['language'], y=books_per_language[books_per_language.supported == 'No']['books'], name='Unsupported languages')
df3 = [trace1, trace2]

updatemenus = list([
    dict(active=1,
         buttons=list([
            dict(label='Log Scale',
                 method='update',
                 args=[{'visible': [True, True]},
                       {'title': 'Number of books (log scale)',
                        'yaxis': {'type': 'log'}}]),
            dict(label='Linear Scale',
                 method='update',
                 args=[{'visible': [True, True]},
                       {'title': 'Number of books (linear scale)',
                        'yaxis': {'type': 'linear'}}])
            ]),
        )
    ])

layout = dict(updatemenus=updatemenus, title='Number of books (Linear scale)')
fig3 = go.Figure(data=df3, layout=layout)

# ------------- Define layout for the app ----------------

app.layout = html.Div([
    dcc.Tabs(id='tabs-nav', value='tab-1', children=[
        dcc.Tab(label='Search engine', value='tab-1'),
        dcc.Tab(label='Statistics', value='tab-2'),
        dcc.Tab(label='Data', value='tab-3'),
        dcc.Tab(label='Discovery mode', value='tab-4'),
        dcc.Tab(label='About', value='tab-5'),
    ]),
    html.Div(id='tabs-content')
])

@app.callback(
    Output('tabs-content', 'children'),
    Input('tabs-nav', 'value')
)              
def render_content(tab):
    if tab == 'tab-1':
        return html.Div([
            html.Div([
                dcc.Markdown('''
                    ## GutenSearch

                    Look inside the books of [Project Gutenberg](https://www.gutenberg.org/).
                
                    '''
                ),
            ], style={'padding': 10, 'text-align': 'center'}),
            html.Div([
                dcc.Markdown('''
                    **Search language:**
                    '''
                ),
                dcc.Dropdown(
                        id='language-dropdown',
                        options=[{'label':language, 'value':language} for language in supported_languages['language']],
                        value='English'),
                dcc.Markdown('''
                    **Search terms:**
                    '''),
                dcc.Input(id='search-terms-input', type='text', value='It was the best of times, it was the worst of times'),
                dcc.Markdown('''
                    **Show this many rows:**
                    '''
                ),
                dcc.Input(
                        id="range-limit", type="number", placeholder="input with range",
                        min=1, max=60000000, step=1, value=10,
                ),
                dcc.Markdown('''
                    **Starting with row:**
                    '''
                ),
                dcc.Input(
                    id="range-offset", type="number", placeholder="input with range",
                    min=1, max=60000000, step=1, value=1,
                ),
            ], style={'columnCount': 4}),    
            html.Div([
                dcc.Markdown('''
                    ###### Press to run:
                    '''
                ),
                html.Button(id='submit-button-state', n_clicks=0, children='Submit'),
            ], style={'padding': 20, 'text-align': 'center'}),
            html.Br(),
            html.Div(id='search-terms-active'),
            html.Br(),
            html.Div(
                id = 'tableDiv',
                className = 'tableDiv'
            ),
            dcc.Loading(
                        id="loading-1",
                        type="default",
                        children=html.Div(id="tableDiv"))
        ], style={'width': '70%', 'margin': 'auto'})
    elif tab == 'tab-2':
        return html.Div([
            html.Div([
                dcc.Markdown('''
                    ## Statistics
                    
                    A look into the raw data.
                    
                    '''
                ),
            ], style={'padding': 10, 'text-align': 'center'}),
            dcc.Markdown('''
            #### Summary statistics
            
            There are 50,729 books in Allison Parrish's [cleaned dataset](https://github.com/aparrish/gutenberg-dammit) of which 1,193 (2.3%) are in languages unsupported by [PostgreSQL's Full Text Search](https://www.postgresql.org/docs/12/textsearch.html), 1312 (2.5%) do not have an author, and 14,503 (29%) do not specify the author's birth and death years. 
            
            #### Operational statistics
            
            Books were split into 61,899,951 paragraphs. Creating a tsvector column on the paragraphs and adding an index on it took 8 hours on a server with 32GB RAM. Whilst the original books and metadata files were around 6 GB, they take 10 GB as a table in PostgreSQL. The paragraphs table with tsvector and index is much larger at 86 GB.
            
            This dropped query time to 20 ms locally, although adding extra information and formatting took the current queries to 200 ms. Dash seems to increase this to between a few seconds and half a minute, in a reliable way that warrants investigation.
            
            #### Books by language
            
            The count of books by language is as follows:
            '''),
            dcc.Graph(
                id='Books by language',
                figure=fig3
            ), 
            html.Div([
                dcc.Markdown('''
                    #### Shortest Path
                    
                    Authors mentioning other authors count as a link between the two, whatever the direction. Find the shortest path between two authors. Because this function does not yet use autocomplete, please check your author name spelling on Project Gutenberg.
                
                    Press to find the shortest path between two authors:
                    '''
                ),
                dcc.Markdown('''
                    **From:**
                    '''),
                dcc.Input(id='from-author', type='text', value='Marcel Proust'),
                dcc.Input(id='to-author', type='text', value='Walter Scott'),
                html.Button(id='from-to-author-button', n_clicks=0, children='Submit'),
                html.Div(id='author-path'),
            ], style={'columnCount': 1}),
            dcc.Markdown('''
            ### Book lengths

            How long are the books in Gutenberg? The following histograms are computed after taking the common logarithm of length (in characters). This is further split by the most common languages. 
            '''),
            dcc.Graph(
                id='Book length histograms',
                figure=fig1
            ),
    ], style={'width': '90%', 'margin': 'auto'})
    elif tab == 'tab-3':
        return html.Div([
            html.Div([
                dcc.Markdown('''
                    ## The data
                    '''
                )
            ], style={'padding': 10, 'text-align': 'center'}),
            html.Div([
                dcc.Markdown('''
                    
                    #### Source
                    
                    Project Gutenberg offers [mirroring via rsync](https://www.gutenberg.org/help/mirroring.html). However, in June 2016, [Allison Parrish](https://www.decontextualize.com/) released a [corpus](https://github.com/aparrish/gutenberg-dammit) of all text files and metadata up to that point in time, which was used here instead of the raw data. 
                    
                    #### Transformation
                    
                    After unpacking the JSON metadata into a table and mapping "?" to NULL, the books could now be inserted, and split using double newline into paragraphs (5 books were further split manually due to still exceeding the [limit for tsvector](https://www.postgresql.org/docs/current/textsearch-limitations.html), which here was around 720,000 characters). 
                    
                    There are some logical inconsistencies in the data such as authors having different birth dates per book, which are left alone for now. Without any information outside the texts and metadata, particularly popularity and academic importance today, search may be less relevant. Some famous quotes occur more often in derivative works than the original. 
                    
                    #### Search
                    
                    The search uses the language in metadata to phraseto_query the indexed column to preserve ordering of the lexemes, which gave far more precise and less numerous results. [Textsearch headline](https://www.postgresql.org/docs/11/textsearch-controls.html#TEXTSEARCH-HEADLINE) with MaxFragments=1000 was used to generate a quote around matched terms which were aggregated per book with the ts_rank_cd averaged across all matched paragraphs. 
                
                    '''
                ),
            ]),
        ], style={'width': '70%', 'margin': 'auto'})
    elif tab == 'tab-4':
        return html.Div([
            html.Div([
                dcc.Markdown('''
                    ## Discovery mode
                    
                    Discover new books!
                
                    '''
                ),
            ], style={'padding': 10, 'text-align': 'center'}),
        html.Div([
            dcc.Markdown('''
                #### How it works
                
                The matching is less strict, and 30 random results from the search are returned instead of the most relevant first.  
                            
                '''
            )
        ]),
        html.Div([
            dcc.Markdown('''
                **Search language:**
                '''
            ),
            dcc.Dropdown(
                    id='discovery-language-dropdown',
                    options=[{'label':language, 'value':language} for language in supported_languages['language']],
                    value='English'),
            dcc.Markdown('''
                **Search terms:**
                '''),
            dcc.Input(id='discovery-search-terms-input', type='text', value='call me Ishmael'),
        ], style={'columnCount': 2}),    
        html.Div([
            dcc.Markdown('''
                ###### Press to run:
                '''
            ),
            html.Button(id='discovery-submit-button-state', n_clicks=0, children='Submit'),
        ], style={'padding': 20, 'text-align': 'center'}),
        html.Br(),
        html.Div(id='discovery-search-terms-active'),
        html.Br(),
        html.Div(
            id = 'discovery-tableDiv',
            className = 'discovery-tableDiv'
        ),
        dcc.Loading(
                    id="loading-2",
                    type="default",
                    children=html.Div(id="discovery-tableDiv"))
    ], style={'width': '70%', 'margin': 'auto'})
    elif tab == 'tab-5':
        return html.Div(
        [
            html.Div([
                dcc.Markdown('''
                    ## About
                    
                    ''')
        ], style={'padding': 10, 'text-align': 'center'}),
        html.Div([
            dcc.Markdown('''
                #### Motivation
                
                Whilst there are plenty of ways to search through Gutenberg titles and authors, I was not aware as of December 2020 of a way to search ***within*** books. You could google the search terms, but this is tricky when you do not know the author and title, particularly to discover new books based on content.
                
                GutenSearch, having indexed the books themselves, can be used precisely for that. Searching for content returns ***all*** books related to that content.  
                
                #### Tech stack and repository
                
                [Dash 1.18](https://plotly.com/dash/) with [PostgreSQL 12](https://www.postgresql.org/docs/12/).
                
                Currently, GutenSearch is closed source as I tidy things, but I plan to release the code and put a pg_dump on a torrent.
                
                #### GDPR, PDPA etc.
                
                I currently track nothing that I know of. I may add a trigger to the database to record the most popular queries so I can take a look at them and improve the search, but it hasn't been done yet and I'll update this section when it happens.
                
                #### Licenses
                
                [Project Gutenberg license](https://www.gutenberg.org/policy/license.html)
                
                The "Gutenberg Dammit" corpus was based off [Julian Brooke's work](http://www.cs.toronto.edu/~jbrooke/gutentag/) at the University of Toronto, which used the following license:
                
                This work is licensed under the Creative Commons Attribution-ShareAlike 4.0 International License. To view a copy of this license, visit https://creativecommons.org/licenses/by-sa/4.0/ or send a letter to Creative Commons, 444 Castro Street, Suite 900, Mountain View, California, 94041, USA.
                
                #### WIP
                
                - Move to the raw data (rsync Project Gutenberg directly).
                - Add where clause parameters (author, year of birth and death, etc.)
                - Resolve search edge cases.
                - Option to use plainto_tsquery for fuzzier matching with more results.
                - Optimisation of Dash.
                - Implementation of ElasticSearch, Solr, Lucene or other "proper" search engine. 
                - Search in one language in a book mostly written in another (e.g. War and Peace opens in French but is in Russian).
                - Try PGroonga, zhparser, pg_bigm or other means of supporting currently unsupported languages.
            
                '''
            )
        ], style={'padding': 10}),
        dcc.Markdown('''
        #### Unsupported languages: 
        '''),
        html.P(unsupported_languages['languages'][0] + '.'),
        dcc.Markdown('''
        '''),
        ], style={'width': '70%', 'margin': 'auto'})

# ------------- Make the app interactive -----------------
@app.callback(
    Output('tableDiv', 'children'),
    Input('submit-button-state', 'n_clicks'), 
    State('language-dropdown', 'value'), 
    State('search-terms-input', 'value'),
    State('range-limit', 'value'),
    State('range-offset', 'value')
)
def update_table(n_clicks, language, search_terms, limit, offset):             
    query = """with paragraphs as (
                select 
                num
                , paragraph
                , ts_rank_cd(textsearchable_index_col, phraseto_tsquery(%s::regconfig, %s), 32) as rank 
                , ts_headline(%s, paragraph, phraseto_tsquery(%s::regconfig, %s), 'MaxFragments=1000, StartSel=**, StopSel=**') as highlighted_result 
                from gutenberg.paragraphs 
                where language = %s::regconfig and textsearchable_index_col @@ phraseto_tsquery(%s::regconfig, %s)
            )
            select b.author
            , '[' || b.title::text || '](https://www.gutenberg.org/ebooks/' || b.num::text || ')' as title
            , '  ...' || substr(string_agg(distinct highlighted_result, E'\n[...]\n'), 1, 10000) || E'...  ' as relevant_paragraphs
            , to_char(100*avg(rank), '99D9') as rank
            from paragraphs a
            inner join gutenberg.all_data b on a.num = b.num
            group by b.author, b.title, b.num
            order by rank desc
            limit %s offset %s;
    """
    connection = engine.connect()
    results = pd.read_sql_query(query, connection, params=[language, search_terms, language, language, search_terms, language, language, search_terms, limit, offset-1])
    connection.close()

    #turn df back into dictionary 
    dict_results= results.iloc[:, 0:3].to_dict('records')
    #Create Table
    tbl = dash_table.DataTable(
        id = 'table',
        style_cell={
                'whiteSpace': 'normal',
                'height': 'auto',
                'textAlign': 'left',
                'font-family':'sans-serif'
            },
        style_cell_conditional=[
                {
                    'if': {'column_id': 'relevant_paragraphs'},
                    'textAlign': 'left'
                }
            ],
        data=dict_results,
        columns=[
            {'name': 'Author', 'id':'author', 'type':'text', 'presentation':'markdown'}, 
            {'name': 'Title', 'id':'title', 'type':'text', 'presentation':'markdown'}, 
            {'name': 'Relevant paragraphs', 'id':'relevant_paragraphs', 'type':'text', 'presentation':'markdown'}, 
        ],
        markdown_options={'link_target': '_blank'},
        filter_action = 'native',
        sort_action = 'native',
        sort_mode = 'multi',
        export_format="csv",
        
    )
    return html.Div([tbl])
    
@app.callback(
    Output('discovery-tableDiv', 'children'),
    Input('discovery-submit-button-state', 'n_clicks'), 
    State('discovery-language-dropdown', 'value'), 
    State('discovery-search-terms-input', 'value')
)
def update_discovery_table(n_clicks, language, search_terms):             
    query = """with paragraphs as (
                select 
                num
                , paragraph
                , ts_headline(%s, paragraph, plainto_tsquery(%s::regconfig, %s), 'MaxFragments=1000, StartSel=**, StopSel=**') as highlighted_result
                from gutenberg.paragraphs 
                where language = %s::regconfig and textsearchable_index_col @@ plainto_tsquery(%s::regconfig, %s)
            )
            select b.author
            , '[' || b.title::text || '](https://www.gutenberg.org/ebooks/' || b.num::text || ')' as title
            , '  ...' || substr(string_agg(distinct highlighted_result, E'\n[...]\n'), 1, 10000) || '...  ' as relevant_paragraphs
            , random() as rand
            from paragraphs a
            inner join gutenberg.all_data b on a.num = b.num
            group by b.author, b.title, b.num
            order by rand desc
            limit 30;
    """
    connection = engine.connect()
    results = pd.read_sql_query(query, connection, params=[language, search_terms, language, language, search_terms, language, language, search_terms])[["author", "title", "relevant_paragraphs"]]
    connection.close()
    #turn df back into dictionary 
    dict_results= results.to_dict('records')
    #Create Table
    tbl = dash_table.DataTable(
        id = 'table',
        style_cell={
                'whiteSpace': 'normal',
                'height': 'auto',
                'textAlign': 'left',
                'font-family':'sans-serif'
            },
        style_cell_conditional=[
                {
                    'if': {'column_id': 'relevant_paragraphs'},
                    'textAlign': 'left'
                }
            ],
        data=dict_results,
        columns=[
            {'name': 'Author', 'id':'author', 'type':'text', 'presentation':'markdown'}, 
            {'name': 'Title', 'id':'title', 'type':'text', 'presentation':'markdown'}, 
            {'name': 'Relevant paragraphs', 'id':'relevant_paragraphs', 'type':'text', 'presentation':'markdown'}, 
            {'name': 'Random', 'id':'rand'}
        ],
        markdown_options={'link_target': '_blank'},
        filter_action = 'native',
        sort_action = 'native',
        sort_mode = 'multi',
        export_format="csv",
        
    )
    return html.Div([tbl])

@app.callback(Output('search-terms-active', 'children'),
              Input('submit-button-state', 'n_clicks'),
              State('language-dropdown', 'value'),
              State('search-terms-input', 'value'),
              State('range-limit', 'value'),
              State('range-offset', 'value'))
def update_output(n_clicks, language, input, range_limit, range_offset):
    return u'''
        Current selection: "{}", "{}" starting with result no. {} for {} rows. Matched words are highlighted. May take up to 30 seconds to load.
    '''.format(language, input, range_offset, range_limit)
    
@app.callback(Output('discovery-search-terms-active', 'children'),
              Input('discovery-submit-button-state', 'n_clicks'),
              State('discovery-language-dropdown', 'value'),
              State('discovery-search-terms-input', 'value'))
def update_output(n_clicks, language, input):
    return u'''
        Current selection: "{}", "{}". Matched words are highlighted. May take up to 30 seconds to load.
    '''.format(language, input)

@app.callback(Output('author-path', 'children'),
              Input('from-to-author-button', 'n_clicks'),
              State('from-author', 'value'),
              State('to-author', 'value'))
def update_author_path(n_clicks, from_author, to_author):
    path = nx.dijkstra_path(mentioned_authors_graph, from_author, to_author)
    return u'''
        Shortest path: "{}".
    '''.format(path, input)

# if running locally, just use localhost (127.0.0.1). You can then run the app by clicking http://127.0.0.1:port/ 
if __name__ == '__main__':
    app.run_server(debug=False, port = [whatever you pass to gunicorn], host='0.0.0.0')