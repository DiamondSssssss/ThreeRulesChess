import re

with open('backend/extra_rules.py', 'r', encoding='utf-8') as f:
    content = f.read()

types = {
    'ghost_pawn': 'on_move',
    'double_step': 'passive',
    'knight_charge': 'on_move',
    'frozen_bishop': 'instant',
    'rook_teleport': 'instant',
    'queen_aura': 'passive',
    'pawn_storm': 'instant',
    'shadow_king': 'passive',
    'explosive_pawn': 'on_move',
    'mirror_board': 'passive',
    'time_warp': 'instant',
    'swap_pieces': 'instant',
    'extra_queen': 'instant',
    'blizzard': 'passive',
    'spy_rook': 'instant',
    'poison_pawn': 'passive',
    'clone_knight': 'instant',
    'reverse_gravity': 'passive',
    'bishop_swap': 'instant',
    'fortify_king': 'passive',
    'random_promotion': 'passive',
    'dark_squares': 'passive',
    'magnet': 'instant',
    'lucky_pawn': 'instant',
    'earthquake': 'instant',
    'shield_wall': 'passive',
    'chaos': 'instant',
    'necromancer': 'passive',
    'timestop': 'instant',
    'grand_exchange': 'instant'
}

for rule_id, rule_type in types.items():
    pattern = r'("id": "' + rule_id + r'",)'
    replacement = r'\1\n        "type": "' + rule_type + r'",'
    content = re.sub(pattern, replacement, content)

with open('backend/extra_rules.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
