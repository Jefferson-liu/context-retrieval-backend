from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)


def main() -> None:
    prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(
                "System prompt with no variables."
            ),
            HumanMessagePromptTemplate.from_template(
                "Document name: {document_name}\n"
                "Document content: {document_content}\n"
            ),
        ]
    )

    formatted = prompt.format_messages(
        document_name="example.md",
        document_content="This is a sample document about TrackRec.",
    )

    for message in formatted:
        print(f"{message.type.upper()}: {message.content}")


if __name__ == "__main__":
    main()
