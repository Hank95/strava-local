"""Main metrics computation orchestration."""

from datetime import datetime
from sqlalchemy.orm import Session

from db.models import Activity, Stream, ActivityMetrics, DailyMetrics
from metrics.profile import get_effective_values, update_estimates
from metrics.tss import compute_activity_tss
from metrics.zones import compute_hr_zones, compute_cardiac_drift, compute_hr_efficiency
from metrics.training_load import compute_training_load
from metrics.aggregations import compute_all_aggregations, compute_rolling_averages


def compute_activity_metrics(
    session: Session,
    activity: Activity,
    profile_values: dict,
    force: bool = False,
) -> ActivityMetrics | None:
    """Compute all metrics for a single activity.

    Args:
        session: Database session
        activity: Activity to process
        profile_values: Profile values from get_effective_values()
        force: If True, recompute even if metrics exist

    Returns:
        ActivityMetrics record (not yet committed)
    """
    # Check if metrics already exist
    existing = session.query(ActivityMetrics).filter_by(activity_id=activity.activity_id).first()
    if existing and not force:
        return existing

    # Get stream data
    stream = session.query(Stream).filter_by(activity_id=activity.activity_id).first()

    # Create or update metrics
    metrics = existing or ActivityMetrics(activity_id=activity.activity_id)
    if not existing:
        session.add(metrics)

    duration = activity.moving_time or activity.elapsed_time or 0

    # Compute TSS
    tss_result = compute_activity_tss(session, activity, stream, profile_values)
    metrics.tss = tss_result["tss"]
    metrics.tss_method = tss_result["tss_method"]
    metrics.trimp = tss_result.get("trimp")
    metrics.has_hr_stream = tss_result["has_hr_stream"]
    metrics.has_power_data = tss_result["has_power_data"]

    # Compute HR zones
    hr_zones = profile_values.get("hr_zones")
    zone_result = compute_hr_zones(stream, hr_zones, duration)
    if zone_result["valid"]:
        metrics.hr_z1_time = zone_result["z1_time"]
        metrics.hr_z2_time = zone_result["z2_time"]
        metrics.hr_z3_time = zone_result["z3_time"]
        metrics.hr_z4_time = zone_result["z4_time"]
        metrics.hr_z5_time = zone_result["z5_time"]
        metrics.aerobic_time = zone_result["aerobic_time"]
        metrics.anaerobic_time = zone_result["anaerobic_time"]

    # Compute cardiac drift
    metrics.cardiac_drift = compute_cardiac_drift(stream, duration)

    # Compute HR efficiency
    metrics.hr_efficiency = compute_hr_efficiency(
        activity.activity_type,
        activity.avg_hr,
        activity.avg_speed,
        activity.avg_watts,
    )

    metrics.computed_at = datetime.utcnow()
    return metrics


def compute_daily_aggregates(session: Session, force: bool = False) -> None:
    """Compute daily aggregates from activity metrics.

    Args:
        session: Database session
        force: If True, recompute all days
    """
    from sqlalchemy import func
    from datetime import timedelta

    # Get all unique activity dates
    dates = (
        session.query(func.date(Activity.start_time))
        .filter(Activity.start_time.isnot(None))
        .distinct()
        .all()
    )

    for (date_val,) in dates:
        if date_val is None:
            continue

        date_str = date_val if isinstance(date_val, str) else date_val.strftime("%Y-%m-%d")

        # Get or create daily metrics
        daily = session.query(DailyMetrics).filter_by(date=date_str).first()
        if daily is None:
            daily = DailyMetrics(date=date_str)
            session.add(daily)
        elif not force:
            continue  # Skip if already computed and not forcing

        # Parse date for filtering
        date_start = datetime.strptime(date_str, "%Y-%m-%d")
        date_end = date_start + timedelta(days=1)

        # Get activities for this day
        activities = (
            session.query(Activity)
            .filter(Activity.start_time >= date_start)
            .filter(Activity.start_time < date_end)
            .all()
        )

        # Aggregate activity data
        daily.activity_count = len(activities)
        daily.total_distance = sum(a.distance or 0 for a in activities)
        daily.total_moving_time = sum(a.moving_time or 0 for a in activities)
        daily.total_elevation = sum(a.elevation_gain or 0 for a in activities)
        daily.total_calories = sum(a.calories or 0 for a in activities)
        daily.has_activity = len(activities) > 0

        # Sum TSS and HR zones from activity_metrics
        activity_ids = [a.activity_id for a in activities]
        if activity_ids:
            metrics_list = (
                session.query(ActivityMetrics)
                .filter(ActivityMetrics.activity_id.in_(activity_ids))
                .all()
            )

            daily.total_tss = sum(m.tss or 0 for m in metrics_list)
            daily.total_hr_z1_time = sum(m.hr_z1_time or 0 for m in metrics_list)
            daily.total_hr_z2_time = sum(m.hr_z2_time or 0 for m in metrics_list)
            daily.total_hr_z3_time = sum(m.hr_z3_time or 0 for m in metrics_list)
            daily.total_hr_z4_time = sum(m.hr_z4_time or 0 for m in metrics_list)
            daily.total_hr_z5_time = sum(m.hr_z5_time or 0 for m in metrics_list)

        daily.computed_at = datetime.utcnow()

    session.commit()


def run_full_computation(
    session: Session,
    force: bool = False,
    quiet: bool = False,
) -> dict:
    """Run the complete metrics computation pipeline.

    Steps:
    1. Update profile estimates from activity data
    2. Compute per-activity metrics (TSS, zones)
    3. Compute daily aggregates
    4. Compute training load (ATL, CTL, TSB)
    5. Compute period aggregations
    6. Compute rolling averages

    Args:
        session: Database session
        force: If True, recompute everything
        quiet: If True, suppress output

    Returns:
        Dict with computation statistics
    """
    stats = {
        "activities_processed": 0,
        "days_computed": 0,
        "errors": [],
    }

    # Step 1: Update profile estimates
    if not quiet:
        print("Updating profile estimates...")
    update_estimates(session)
    profile_values = get_effective_values(session)

    if not quiet:
        max_hr = profile_values.get("max_hr")
        lthr = profile_values.get("lthr")
        print(f"  Max HR: {max_hr}, LTHR: {lthr}")

    # Step 2: Compute per-activity metrics
    if not quiet:
        print("Computing activity metrics...")

    activities = session.query(Activity).all()
    for i, activity in enumerate(activities):
        try:
            compute_activity_metrics(session, activity, profile_values, force=force)
            stats["activities_processed"] += 1

            if not quiet and (i + 1) % 100 == 0:
                print(f"  Processed {i + 1}/{len(activities)} activities...")

        except Exception as e:
            stats["errors"].append(f"Activity {activity.activity_id}: {e}")

    session.commit()

    if not quiet:
        print(f"  Processed {stats['activities_processed']} activities")

    # Step 3: Compute daily aggregates
    if not quiet:
        print("Computing daily aggregates...")
    compute_daily_aggregates(session, force=force)

    # Step 4: Compute training load
    if not quiet:
        print("Computing training load (ATL/CTL/TSB)...")
    compute_training_load(session, force_recompute=force)

    # Count days
    stats["days_computed"] = session.query(DailyMetrics).count()
    if not quiet:
        print(f"  Computed {stats['days_computed']} days")

    # Step 5: Compute period aggregations
    if not quiet:
        print("Computing period aggregations...")
    compute_all_aggregations(session, force_recompute=force)

    # Step 6: Compute rolling averages
    if not quiet:
        print("Computing rolling averages...")
    compute_rolling_averages(session, force_recompute=force)

    if not quiet:
        print("Done!")
        if stats["errors"]:
            print(f"  {len(stats['errors'])} errors occurred")

    return stats
