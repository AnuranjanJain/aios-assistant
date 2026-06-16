import uvicorn


def main():
    uvicorn.run("automation_agent.api:app", host="127.0.0.1", port=5065, reload=False)


if __name__ == "__main__":
    main()
