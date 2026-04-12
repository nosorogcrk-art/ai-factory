"from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get('/hello')\nasync def hello():\n    return {'message': 'Hello, World!'}\n"
