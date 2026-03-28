from pkbot.actions import ActionFold, ActionCall, ActionCheck, ActionRaise, ActionPass
from pkbot.states import GameInfo, PokerState
from pkbot.base import BaseBot
from pkbot.runner import parse_args, run_bot
import random

class Player(BaseBot):
    def __init__(self) -> None:
        pass

    def on_hand_start(self, game_info: GameInfo, current_state: PokerState) -> None:
        pass

    def on_hand_end(self, game_info: GameInfo, current_state: PokerState) -> None:
        pass

    def get_move(self, game_info: GameInfo, current_state: PokerState):
        if current_state.street == 'TriplePass':
            return ActionPass(sorted(random.sample(range(0, len(current_state.my_hand)), 3)))
        elif current_state.street == 'DoublePass':
            return ActionPass(sorted(random.sample(range(0, len(current_state.my_hand)), 2)))
        elif current_state.street == 'SinglePass':
            return ActionPass(sorted(random.sample(range(0, len(current_state.my_hand)), 1)))
        
        if current_state.can_act(ActionCheck):
            return ActionCheck()
        return ActionCall()

if __name__ == '__main__':
    run_bot(Player(), parse_args())
