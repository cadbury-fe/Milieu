from __future__ import annotations

from app.data.database.components import ComponentType
from app.data.database.database import DB
from app.data.database.skill_components import SkillComponent, SkillTags
from app.engine import (action, banner, combat_calcs, engine, equations,
                        image_mods, item_funcs, item_system, skill_system,
                        target_system)
from app.engine.game_state import game
from app.engine.objects.unit import UnitObject
from app.utilities import utils, static_random
from app.utilities.enums import Strike


class DoNothing(SkillComponent):
    nid = 'do_nothing'
    desc = 'does nothing'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 1

class Powerstaff(SkillComponent):
	nid = 'powerstaff'
	desc = 'After using a staff, unit can move again.'
	tag = SkillTags.MOVEMENT
	
	def end_combat(self, playback, unit, item, target, item2, mode):
		playbacks = [p for p in playback if p.nid in ('mark_hit', 'heal_hit') ]
		if item_system.weapon_type(unit, item) == 'Staff' and any(p.attacker is unit for p in playbacks):
			action.do(action.Reset(unit))
			action.do(action.TriggerCharge(unit, self.skill))
	
class GiveBacker(SkillComponent):
	nid = 'givebacker'
	desc = "Adds damage equal to HP lost."
	tag = SkillTags.COMBAT

	def modify_damage(self, unit, item):
		value = unit.get_max_hp() - unit.get_hp()
		return value

class SecondWind(SkillComponent):
    nid = 'second_wind'
    desc = 'If the unit misses an attack, unit can move again'
    tag = SkillTags.MOVEMENT
	
    def end_combat(self, playback, unit, item, target, item2, mode):
        playbacks = [p for p in playback if p.nid in ('mark_miss')]
        if any(p.attacker is unit for p in playbacks):
            action.do(action.Reset(unit))
            action.do(action.TriggerCharge(unit, self.skill))

class EvalGaleforce(SkillComponent):
    nid = 'eval_galeforce'
    desc = "Unit can move again if conditions are met. Value must resolve to a Boolean."
    tag = SkillTags.CUSTOM

    expose = ComponentType.String
    value = ''
    author = 'Lord_Tweed'

    def end_combat(self, playback, unit, item, target, item2, mode):
        from app.engine import evaluate
        try:
            x = bool(evaluate.evaluate(self.value, unit, target, unit.position, {'item': item, 'item2': item2, 'mode': mode}))
            if x:
                action.do(action.Reset(unit))
                action.do(action.TriggerCharge(unit, self.skill))
        except Exception as e:
            print("%s: Could not evaluate EvalGaleforce condition %s" % (e, self.value))

class EventWhenHit(SkillComponent):
    nid = 'event_when_hit'
    desc = 'Calls event when unit is hit'
    tag = SkillTags.ADVANCED

    expose = ComponentType.Event
    value = ''
    
    def after_take_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        if strike == Strike.HIT or strike == Strike.CRIT:
            game.events.trigger_specific_event(self.value, unit, target, unit.position, {'item': item, 'mode': mode, 'item2': item2})

class EventAfterStrike(SkillComponent):
    nid = 'event_after_strike'
    desc = 'Calls event when unit makes an attack'
    tag = SkillTags.ADVANCED

    expose = ComponentType.Event
    value = ''
    
    def after_strike(self, actions, playback, unit, item, target, item2, mode, attack_info, strike):
        game.events.trigger_specific_event(self.value, unit, target, unit.position, {'item': item, 'mode': mode, 'item2': item2})