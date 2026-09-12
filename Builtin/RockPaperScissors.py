import random
def rock_paper_scissors():
    choices = ["rock", "paper", "scissors"]
    user_choice = input("> Rock, paper or scissors? > ").lower()
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
try:
    while True:
        rock_paper_scissors()
except KeyboardInterrupt:
    print("\nExiting..")