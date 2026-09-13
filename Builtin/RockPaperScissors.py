import random
def rock_paper_scissors():
    choices = ["rock", "paper", "scissors"]
    try:
        user_choice = input("> Rock, paper or scissors? (type 'quit' to exit) > ").lower().strip()
    except (EOFError, KeyboardInterrupt):
        print("\n> Exiting RPS...")
        raise
    if user_choice in ("quit", "exit", "q", "back", "leave", "stop", "end"):
        print("> Exiting RPS... bye!")
        raise SystemExit
    computer_choice = random.choice(choices)
    if user_choice not in choices:
        print("> Invalid choice buddy!, please choose rock, paper or scissors.")
        return
    elif user_choice == computer_choice:
        print(f"> Both players selected {user_choice}. It's a tie!")
    elif user_choice == "rock":
        if computer_choice == "scissors":
            print("> Rock smashes scissors! You win!")
        else:
            print("> Paper covers rock! You lose.")
    elif user_choice == "paper":
        if computer_choice == "rock":
            print("> Paper covers rock! You win!")
        else:
            print("> Scissors cuts paper! You lose.")
    elif user_choice == "scissors":
        if computer_choice == "paper":
            print("> Scissors cuts paper! You win!")
        else:
            print("> Rock smashes scissors! You lose.")
    return computer_choice, user_choice

if __name__ == "__main__":
    try:
        while True:
            rock_paper_scissors()
    except (KeyboardInterrupt, EOFError, SystemExit):
        print("\nExiting..")