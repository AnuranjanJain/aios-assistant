import uvicorn


def main():
    uvicorn.run("career_agent.api:app", host="127.0.0.1", port=5067, reload=False)


if __name__ == "__main__":
    main()
