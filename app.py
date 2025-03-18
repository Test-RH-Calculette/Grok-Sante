from flask import Flask, render_template, request, jsonify
import sqlite3
import re
from datetime import datetime
import pandas as pd
import plotly.express as px
import os

app = Flask(__name__)

# Initialisation de la base de données
def init_db():
    conn = sqlite3.connect('healthcare.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reimbursements
                 (id INTEGER PRIMARY KEY,
                  care_date TEXT,
                  care_type TEXT,
                  care_code TEXT,
                  paid_amount REAL,
                  reimbursement_base REAL,
                  reimbursed_amount REAL,
                  complementary_rate TEXT,
                  complementary_amount REAL)''')
    conn.commit()
    conn.close()

# Fonction d'extraction des données
def extract_data(content):
    pattern = r'(\d{2}/\d{2}/\d{4})\s+([A-Z\s\.]+)\s+\((.+?)\)\s+(\d+,\d+)\s+(\d+,\d+)\s+(\d+%)\s+(\d+,\d+)\s+(\d+%)'
    matches = re.findall(pattern, content)
    
    results = []
    for match in matches:
        care = {
            'care_date': match[0],
            'care_type': match[1].strip(),
            'care_code': match[2],
            'paid_amount': float(match[3].replace(',', '.')),
            'reimbursement_base': float(match[4].replace(',', '.')),
            'reimbursed_amount': float(match[6].replace(',', '.')),
            'complementary_rate': match[7],
            'complementary_amount': float(match[5].replace(',', '.'))
        }
        results.append(care)
    return results

# Sauvegarde dans la base de données
def save_to_db(care_list):
    conn = sqlite3.connect('healthcare.db')
    c = conn.cursor()
    for care in care_list:
        c.execute('''INSERT INTO reimbursements 
                    (care_date, care_type, care_code, paid_amount, reimbursement_base, 
                     reimbursed_amount, complementary_rate, complementary_amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                 (care['care_date'], care['care_type'], care['care_code'],
                  care['paid_amount'], care['reimbursement_base'], care['reimbursed_amount'],
                  care['complementary_rate'], care['complementary_amount']))
    conn.commit()
    conn.close()

@app.route('/')
def upload_file():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def process_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    content = file.read().decode('utf-8')
    
    extracted_data = extract_data(content)
    save_to_db(extracted_data)
    
    return jsonify(extracted_data)

@app.route('/dashboard')
def dashboard():
    conn = sqlite3.connect('healthcare.db')
    df = pd.read_sql_query("SELECT * FROM reimbursements", conn)
    conn.close()
    
    # Préparation des données pour le graphique
    df['care_date'] = pd.to_datetime(df['care_date'], format='%d/%m/%Y')
    monthly_data = df.groupby(df['care_date'].dt.to_period('M'))['paid_amount'].sum().reset_index()
    monthly_data['care_date'] = monthly_data['care_date'].dt.to_timestamp()
    
    # Création du graphique
    fig = px.line(monthly_data, x='care_date', y='paid_amount', 
                 title='Dépenses mensuelles de soins')
    graph_json = fig.to_json()
    
    return render_template('dashboard.html', 
                         table_data=df.to_dict('records'),
                         graph_json=graph_json)

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))  # Par défaut 5000 en local
    app.run(host='0.0.0.0', port=port, debug=False)
