from flask import Flask, request, jsonify
import asyncio
from search_utils import get_search_results, extract_website_info

app = Flask(__name__)

@app.route('/search', methods=['POST'])
def search():
    """
    Endpoint to perform a search based on a query.
    """
    data = request.json
    query = data.get('query', '')
    max_questions = data.get('max_questions', 5)
    max_websites = data.get('max_websites', 3)
    
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400
    
    try:
        result = asyncio.run(get_search_results(query, max_questions, max_websites))
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/extract', methods=['POST'])
def extract():
    """
    Endpoint to extract website information.
    """
    data = request.json
    url = data.get('url', '')
    
    if not url:
        return jsonify({"error": "URL parameter is required"}), 400
    
    try:
        website_info = extract_website_info(url)
        if website_info:
            return jsonify(website_info), 200
        else:
            return jsonify({"error": "Failed to extract content"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
