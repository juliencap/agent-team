from langchain.agents import create_agent
def main():

    def get_weather(city: str) -> str:
        """Get weather for a given city."""
        return f"It's always sunny in {city}!"

    agent = create_agent(
        model="openai:gpt-5.4",
        tools=[],
        system_prompt="""
        Tu es un agent qui aide à la prise de rendez-vous patient dans une clinique où il y a plusieurs médecins générals
        Tu réponds à la demande des patients pour attribuer des rendez-vous en fonction des disponibilités
        """,
    )

    result = agent.invoke(
        {"messages": [{"role": "user", "content": "What's the weather in San Francisco?"}]}
    )
    print(result["messages"][-1].content_blocks)


if __name__ == "__main__":
    main()

