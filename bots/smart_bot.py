import random
import itertools
from pkbot.actions import ActionFold, ActionCall, ActionCheck, ActionRaise, ActionPass
from pkbot.states import GameInfo, PokerState
from pkbot.base import BaseBot
from pkbot.runner import parse_args, run_bot

try:
    import eval7
except ImportError:
    eval7 = None

class Player(BaseBot):
    def __init__(self) -> None:
        pass

    def on_hand_start(self, game_info: GameInfo, current_state: PokerState) -> None:
        pass

    def on_hand_end(self, game_info: GameInfo, current_state: PokerState) -> None:
        pass

    def get_eval7_cards(self, cards_list):
        if eval7 is None:
            return []
        return [eval7.Card(s) for s in set(cards_list)]

    def _get_card_trash_score(self, card_str):
        # Fallback heuristic: single card strength
        rank_str = card_str[0]
        rank_val = "23456789TJQKA".find(rank_str) + 2
        return rank_val

    def get_pass_indices(self, my_hand_strs, num_pass):
        if eval7 is None:
            # Fallback: pass the lowest cards
            scored = [(self._get_card_trash_score(c), idx) for idx, c in enumerate(my_hand_strs)]
            scored.sort()
            return [idx for _, idx in scored[:num_pass]]
        
        cards = [eval7.Card(s) for s in my_hand_strs]
        best_core_score = -1
        best_core_indices = set()
        
        # Find the best 5-card combination
        # comb(7, 5) = 21 combinations, lightning fast
        for combo_indices in itertools.combinations(range(len(cards)), 5):
            combo_cards = [cards[i] for i in combo_indices]
            score = eval7.evaluate(combo_cards)
            if score > best_core_score:
                best_core_score = score
                best_core_indices = set(combo_indices)
                
        # The 2 cards NOT in our optimal 5-card hand are absolute trash to us.
        trash_indices = [i for i in range(len(cards)) if i not in best_core_indices]
        
        if num_pass > len(trash_indices):
            # Sort the core indices by their individual rank. We pick the lowest one to discard.
            core_scored = [(self._get_card_trash_score(my_hand_strs[i]), i) for i in best_core_indices]
            core_scored.sort()
            needed = num_pass - len(trash_indices)
            trash_indices.extend([i for _, i in core_scored[:needed]])
            
        # Ensure we only pass the `num_pass` worst cards
        return sorted(trash_indices[:num_pass])

    def get_move(self, game_info: GameInfo, current_state: PokerState):
        street = current_state.street
        my_hand = current_state.my_hand
        
        if street == 'TriplePass':
            return ActionPass(self.get_pass_indices(my_hand, 3))
        elif street == 'DoublePass':
            return ActionPass(self.get_pass_indices(my_hand, 2))
        elif street == 'SinglePass':
            return ActionPass(self.get_pass_indices(my_hand, 1))
            
        # Betting logic
        if eval7 is None:
            if current_state.can_act(ActionCall): return ActionCall()
            return ActionCheck()

        cards = [eval7.Card(s) for s in my_hand]
        score = eval7.evaluate(cards)
        hand_type = eval7.handtype(score)
        
        # Very small bluff frequency (5%) on the final street or randomly
        if random.random() < 0.05 and current_state.can_act(ActionRaise):
            min_r, _ = current_state.raise_bounds
            return ActionRaise(min_r)

        # Baseline Anaconda Strengths
        # Hands are much stronger in Anaconda since everyone makes 5 from 7, with trades.
        monster = hand_type in ['Full House', 'Four of a Kind', 'Straight Flush']
        strong = hand_type in ['Straight', 'Flush']
        marginal = hand_type in ['Two Pair', 'Three of a Kind']
        
        pot = current_state.pot
        cost_to_call = getattr(current_state, 'cost_to_call', 0)
        
        if monster:
            if current_state.can_act(ActionRaise):
                min_r, max_r = current_state.raise_bounds
                # Value bet: up to half pot + min_raise
                target_raise = max(min_r, min(max_r, int(pot * 0.5) + min_r))
                return ActionRaise(target_raise)
            if current_state.can_act(ActionCall):
                return ActionCall()

        elif strong:
            # Raise lightly if no huge bets, otherwise call
            if current_state.can_act(ActionRaise) and cost_to_call < pot // 2:
                min_r, max_r = current_state.raise_bounds
                return ActionRaise(min_r)
            if current_state.can_act(ActionCall):
                return ActionCall()

        elif marginal:
            # Call standard bets, fold to massive overbets
            if cost_to_call > pot:
                if current_state.can_act(ActionFold):
                    return ActionFold()
            if current_state.can_act(ActionCall):
                return ActionCall()

        else:
            # Weak Hand (High Card, Pair): fold to any aggression
            if cost_to_call > 0 and current_state.can_act(ActionFold):
                return ActionFold()
            if current_state.can_act(ActionCheck):
                return ActionCheck()

        # Final Fallback
        if current_state.can_act(ActionCheck):
            return ActionCheck()
        if current_state.can_act(ActionCall):
            return ActionCall()
        return ActionFold()

if __name__ == '__main__':
    run_bot(Player(), parse_args())
