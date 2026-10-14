# phase2/text_to_sign.py

"""
Text to Sign Converter Module
-----------------------------
This program takes a sentence from the user, converts it to uppercase,
splits it into words, looks up signs in SIGN_DICTIONARY, and outputs:
1. Recognized signs in order with their video asset filenames.
2. Unsupported words for which no sign exists.
"""

import string
try:
    from sign_dictionary import SIGN_DICTIONARY
except ModuleNotFoundError:
    from phase2.sign_dictionary import SIGN_DICTIONARY


def text_to_sign(sentence: str):
    """
    Converts input sentence into recognized signs and unsupported words.

    Args:
        sentence (str): Input text from the user.

    Returns:
        tuple: (recognized_signs, unsupported_words)
    """
    # Convert sentence to uppercase
    uppercase_sentence = sentence.upper()

    # Remove punctuation for clean matching
    cleaned_sentence = uppercase_sentence.translate(str.maketrans('', '', string.punctuation))

    # Split sentence into words
    words = cleaned_sentence.split()

    recognized_signs = []
    unsupported_words = []

    i = 0
    while i < len(words):
        # Check two-word phrases first (e.g., "THANK YOU")
        if i + 1 < len(words):
            two_word_phrase = f"{words[i]} {words[i + 1]}"
            if two_word_phrase in SIGN_DICTIONARY:
                recognized_signs.append((two_word_phrase, SIGN_DICTIONARY[two_word_phrase]))
                i += 2
                continue

        # Check single word against dictionary
        word = words[i]
        if word in SIGN_DICTIONARY:
            recognized_signs.append((word, SIGN_DICTIONARY[word]))
        else:
            unsupported_words.append(word)
        i += 1

    return recognized_signs, unsupported_words


def main():
    user_input = input("Input:\n").strip()

    if not user_input:
        print("No text entered.")
        return

    recognized_signs, unsupported_words = text_to_sign(user_input)

    if recognized_signs:
        print("\nRecognized signs:")
        for word, filename in recognized_signs:
            print(f"{word} -> {filename}")

    if unsupported_words:
        print("\nUnsupported words:")
        for word in unsupported_words:
            print(word)


if __name__ == "__main__":
    main()
