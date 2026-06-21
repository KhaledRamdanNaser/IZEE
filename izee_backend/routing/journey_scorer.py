MODE_COSTS = {
    "metro": -300,
    "lrt": -220,
    "brt": -180,
    "bus": 0,
    "minibus": 120,
    "microbus": 180,
}
BACKBONE_MODES = {"metro", "lrt", "brt"}
SURFACE_MODES = {"bus", "minibus", "microbus"}
MODE_SWITCH_PENALTY = 300
BACKBONE_EXIT_PENALTY = 600
EXTRA_FRAGMENTED_LEG_PENALTY = 250


def calculate_path_stats(path):
    transit_leg_count = 0
    walking_time = 0
    waiting_time = 0

    for leg in path:
        if leg["mode"] == "walk":
            walking_time += int(leg.get("walking_time", 0))
        else:
            transit_leg_count += 1
            waiting_time += int(leg.get("waiting_time", 0))

    transfer_count = max(0, transit_leg_count - 1)

    return {
        "transit_leg_count": transit_leg_count,
        "transfer_count": transfer_count,
        "walking_time": walking_time,
        "waiting_time": waiting_time,
    }


def calculate_mode_adjustment(path):
    adjustment = 0
    breakdown = {}

    for leg in path:
        mode = leg.get("mode")

        if mode == "walk":
            continue

        mode_cost = MODE_COSTS.get(mode, 0)
        adjustment += mode_cost
        breakdown[mode] = breakdown.get(mode, 0) + mode_cost

    return adjustment, breakdown


def get_transit_modes(path):
    return [
        leg.get("mode")
        for leg in path
        if leg.get("mode") != "walk"
    ]


def calculate_mode_switch_penalty(path):
    transit_modes = get_transit_modes(path)
    penalty = 0
    breakdown = {
        "mode_switch_count": 0,
        "backbone_exit_count": 0,
        "extra_fragmented_leg_count": max(0, len(transit_modes) - 2),
    }

    for previous_mode, next_mode in zip(transit_modes, transit_modes[1:]):
        if previous_mode == next_mode:
            continue

        penalty += MODE_SWITCH_PENALTY
        breakdown["mode_switch_count"] += 1

        if previous_mode in BACKBONE_MODES and next_mode in SURFACE_MODES:
            penalty += BACKBONE_EXIT_PENALTY
            breakdown["backbone_exit_count"] += 1

    penalty += (
        breakdown["extra_fragmented_leg_count"]
        * EXTRA_FRAGMENTED_LEG_PENALTY
    )

    return penalty, breakdown


def score_journey(
    travel_time: int,
    waiting_time: int,
    walking_time: int,
    transfer_count: int,
    final_walking_time: int = 0,
    mode_adjustment: int = 0,
    mode_switch_penalty: int = 0,
):
    breakdown = {
        "travel_time": travel_time,
        "waiting_penalty": waiting_time * 1.5,
        "walking_penalty": walking_time * 2.0,
        "transfer_penalty": transfer_count * 600,
        "final_walking_penalty": final_walking_time * 2.5,
        "mode_adjustment": mode_adjustment,
        "mode_switch_penalty": mode_switch_penalty,
    }

    return {
        "total_cost": sum(breakdown.values()),
        "breakdown": breakdown,
    }


def score_path(path, total_travel_time, final_walking_time=0):
    transit_leg_count = 0
    walking_time = 0
    waiting_time = 0
    mode_adjustment = 0
    mode_breakdown = {}
    previous_transit_mode = None
    mode_switch_penalty = 0
    mode_switch_count = 0
    backbone_exit_count = 0

    for leg in path:
        mode = leg.get("mode")

        if mode == "walk":
            walking_time += int(leg.get("walking_time", 0))
            continue

        transit_leg_count += 1
        waiting_time += int(leg.get("waiting_time", 0))

        mode_cost = MODE_COSTS.get(mode, 0)
        mode_adjustment += mode_cost
        mode_breakdown[mode] = mode_breakdown.get(mode, 0) + mode_cost

        if previous_transit_mode is not None and previous_transit_mode != mode:
            mode_switch_penalty += MODE_SWITCH_PENALTY
            mode_switch_count += 1

            if previous_transit_mode in BACKBONE_MODES and mode in SURFACE_MODES:
                mode_switch_penalty += BACKBONE_EXIT_PENALTY
                backbone_exit_count += 1

        previous_transit_mode = mode

    transfer_count = max(0, transit_leg_count - 1)
    extra_fragmented_leg_count = max(0, transit_leg_count - 2)
    mode_switch_penalty += (
        extra_fragmented_leg_count
        * EXTRA_FRAGMENTED_LEG_PENALTY
    )
    stats = {
        "transit_leg_count": transit_leg_count,
        "transfer_count": transfer_count,
        "walking_time": walking_time,
        "waiting_time": waiting_time,
    }
    has_transit = stats["transit_leg_count"] > 0
    effective_final_walking_time = final_walking_time if has_transit else 0
    mode_switch_breakdown = {
        "mode_switch_count": mode_switch_count,
        "backbone_exit_count": backbone_exit_count,
        "extra_fragmented_leg_count": extra_fragmented_leg_count,
    }
    score = score_journey(
        travel_time=total_travel_time,
        waiting_time=stats["waiting_time"],
        walking_time=stats["walking_time"],
        transfer_count=stats["transfer_count"],
        final_walking_time=effective_final_walking_time,
        mode_adjustment=mode_adjustment,
        mode_switch_penalty=mode_switch_penalty,
    )

    score["mode_breakdown"] = mode_breakdown
    score["mode_switch_breakdown"] = mode_switch_breakdown
    score["stats"] = stats

    return score
