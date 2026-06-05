# clean.py
with open("streamlit_app.py", "r", encoding="utf-8") as f:
    text = f.read()

# Replace all invisible non-breaking spaces with standard normal spaces
cleaned_text = text.replace("\xa0", " ")

with open("streamlit_app.py", "w", encoding="utf-8") as f:
    f.write(cleaned_text)

print("✨ All invisible formatting characters successfully removed!")
