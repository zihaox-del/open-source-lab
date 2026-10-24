import uvicorn

if __name__ == '__main__':
    uvicorn.run('websheet.app:create_app', factory=True, host='127.0.0.1', port=8765, workers=1, access_log=False)
