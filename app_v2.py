from flask import Flask, request, render_template, redirect, url_for, Response
import os
import re
import subprocess
import io
import csv
import math
from collections import Counter

import mysql.connector
import pandas as pd

app = Flask(__name__)

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'crawlingdata_db'
}

# Isi token X di sini sebelum menjalankan crawling.
TWITTER_AUTH_TOKEN = 'Isi token X'


def get_next_time_slot(cursor, conn):
    cursor.execute("SELECT kaunter FROM kaunter")
    result = cursor.fetchone()
    current = int(result[0]) if result else 0
    if result is None:
        cursor.execute("INSERT INTO kaunter (kaunter) VALUES (0)")
    next_slot = current + 1
    cursor.execute("UPDATE kaunter SET kaunter = %s WHERE kaunter = %s", (next_slot, current))
    conn.commit()
    return next_slot


def clean_text(text):
    text = re.sub(r'http\S+', '', str(text).lower())
    text = re.sub(r'@[A-Za-z0-9_]+', '', text)
    return re.sub(r'[^a-z0-9\s]', '', text).strip()


def insert_dataframe(df, keyword):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    time_slot = get_next_time_slot(cursor, conn)
    count = 0
    try:
        for _, row in df.iterrows():
            text = row.get('full_text')
            if pd.isna(text) or not str(text).strip():
                text = row.get('tweet_text') or row.get('text')
            if pd.isna(text) or not str(text).strip():
                continue

            text = str(text)
            username = row.get('username', 'unknown')
            created_at = row.get('created_at')
            processed_text = clean_text(text)

            cursor.execute(
                "INSERT INTO tweets (keyword, username, tweet_text, created_at) "
                "VALUES (%s, %s, %s, %s)",
                (keyword, username, text, created_at))
            cursor.execute(
                "INSERT INTO twitter (time_slot, keyword, username, waktu, isi_twit, processed_text) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (time_slot, keyword, username, created_at, text, processed_text))
            count += 1
        conn.commit()
        return count, time_slot
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


@app.route('/')
def index():
    return render_template('index.html')


def fetch_twitter_rows(keyword=None):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT id, time_slot, keyword, username, waktu, isi_twit, processed_text
            FROM twitter
        """
        params = []
        if keyword:
            query += " WHERE keyword = %s"
            params.append(keyword)
        query += " ORDER BY id ASC"
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


@app.route('/data')
def data():
    keyword = request.args.get('keyword', '').strip()
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT keyword FROM twitter WHERE keyword IS NOT NULL ORDER BY keyword")
        keywords = [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()
    rows = fetch_twitter_rows(keyword or None)
    query = request.args.get('query', '').strip().lower()
    tfidf = calculate_tfidf(rows, query)
    return render_template('index.html', rows=rows, keywords=keywords,
                           selected_keyword=keyword, query=query, tfidf=tfidf,
                           show_data=True)


def calculate_tfidf(rows, query):
    if not query:
        return None
    documents = []
    for row in rows:
        words = (row.get('processed_text') or '').lower().split()
        if words:
            documents.append((row, words))
    if not documents:
        return {'query': query, 'total_documents': 0, 'matching_documents': 0,
                'idf': 0, 'results': []}

    total_documents = len(documents)
    matching_documents = sum(query in words for _, words in documents)
    if matching_documents == 0:
        return {'query': query, 'total_documents': total_documents,
                'matching_documents': 0, 'idf': 0, 'results': []}

    idf = math.log10(total_documents / matching_documents)
    results = []
    for row, words in documents:
        tf = words.count(query) / len(words)
        results.append({
            'id': row['id'],
            'text': row.get('processed_text') or '',
            'tf': tf,
            'idf': idf,
            'tfidf': tf * idf,
        })
    return {'query': query, 'total_documents': total_documents,
            'matching_documents': matching_documents, 'idf': idf,
            'results': results}


@app.route('/data/csv')
def data_csv():
    keyword = request.args.get('keyword', '').strip()
    rows = fetch_twitter_rows(keyword or None)
    output = io.StringIO()
    writer = csv.writer(output)
    columns = ('id', 'time_slot', 'keyword', 'username', 'waktu', 'isi_twit', 'processed_text')
    writer.writerow(columns)
    writer.writerows(tuple(row[column] for column in columns) for row in rows)
    filename = f"twitter_{keyword or 'semua'}.csv"
    return Response(output.getvalue(), mimetype='text/csv', headers={
        'Content-Disposition': f'attachment; filename="{filename}"'
    })


@app.route('/crawl', methods=['POST'])
def crawl():
    keyword = request.form['keyword'].strip()
    limit = request.form['limit']
    start_date = request.form['start_date']
    end_date = request.form['end_date']
    filename = f"{keyword.replace(' ', '_')}.csv"
    command = [
        'npx.cmd', '--yes', 'tweet-harvest@latest', '-o', filename,
        '-s', f'{keyword} since:{start_date} until:{end_date} lang:id',
        '--tab', 'LATEST', '-l', str(limit),
        '--token', TWITTER_AUTH_TOKEN
    ]
    try:
        subprocess.run(command, check=True, text=True)
        filepath = os.path.join('tweets-data', filename)
        if not os.path.exists(filepath):
            return f"File {filepath} tidak ditemukan.<br><a href='/'>Kembali</a>"
        count, time_slot = insert_dataframe(pd.read_csv(filepath), keyword)
        return redirect(url_for('data'))
    except Exception as err:
        return f"<h3>Error:</h3><p>{err}</p><a href='/'>Kembali</a>"


if __name__ == '__main__':
    app.run(debug=True)