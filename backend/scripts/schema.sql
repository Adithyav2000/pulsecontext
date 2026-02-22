-- ============================================================================
-- PulseContext: Normalized SQL Schema for Morning Commute Intelligence
-- ============================================================================
-- Supports 8 use cases: 
--   1. Morning Commute Intelligence
--   2. Stress-Aware Break Recommendation
--   3. Gym Pattern Prediction
--   4. Fatigue Detection
--   5. Habit Reinforcement Engine
--   6. Time-Waste Pattern Detection (future)
--   7. Proactive Calendar Optimization
--   8. Cross-Device Unified Health Context
--
-- Use: psql -U pulse -d pulsecontext < schema.sql
-- ============================================================================

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Users: Central entity
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    name TEXT,
    timezone TEXT DEFAULT 'America/New_York',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Health Records: Denormalized raw metrics from exported data
CREATE TABLE IF NOT EXISTS health_record (
    record_id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    record_type TEXT NOT NULL,  -- e.g., HKQuantityTypeIdentifierHeartRate
    source TEXT NOT NULL,        -- e.g., Apple Watch, iPhone, Oura
    ts TIMESTAMP WITH TIME ZONE NOT NULL,
    value NUMERIC NOT NULL,
    unit TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_health_record_user_ts ON health_record(user_id, ts DESC);
CREATE INDEX idx_health_record_type ON health_record(record_type);
CREATE INDEX idx_health_record_source ON health_record(source);

-- Workouts: Structured exercise sessions
CREATE TABLE IF NOT EXISTS workouts (
    workout_id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    activity_type TEXT NOT NULL,  -- e.g., Walking, Running, Gym, Cycling
    start_ts TIMESTAMP WITH TIME ZONE NOT NULL,
    end_ts TIMESTAMP WITH TIME ZONE,
    duration_minutes INT,
    calories_burned NUMERIC,
    intensity_level TEXT,  -- light, moderate, vigorous
    source TEXT,
    location_cluster_id BIGINT,  -- FK to location_clusters (below)
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_workouts_user_ts ON workouts(user_id, start_ts DESC);

-- Calendar Events: Integration with user calendar (for future use)
CREATE TABLE IF NOT EXISTS calendar_events (
    event_id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title TEXT,
    description TEXT,
    start_ts TIMESTAMP WITH TIME ZONE NOT NULL,
    end_ts TIMESTAMP WITH TIME ZONE,
    duration_minutes INT,
    stress_category TEXT,  -- meeting, deep_work, break, commute, exercise
    is_recurring BOOLEAN DEFAULT FALSE,
    external_id TEXT,  -- for sync with Google Calendar, Outlook, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_calendar_user_ts ON calendar_events(user_id, start_ts DESC);

-- Location Clusters: Geographic regions (home, work, gym, etc.)
CREATE TABLE IF NOT EXISTS location_clusters (
    cluster_id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name TEXT NOT NULL,  -- e.g., Home Office, Gym, Commute Route A
    inferred_type TEXT,  -- home, work, gym, commute, other
    latitude NUMERIC(10, 8),
    longitude NUMERIC(11, 8),
    radius_meters NUMERIC,
    visit_frequency_7day INT DEFAULT 0,
    avg_visit_duration_min INT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_location_clusters_user ON location_clusters(user_id);

-- ============================================================================
-- COMPUTED/AGGREGATION TABLES (for query optimization)
-- ============================================================================

-- Daily Summary: Rolled-up daily metrics
CREATE TABLE IF NOT EXISTS daily_summary (
    summary_id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    
    -- Sleep metrics
    sleep_duration_hours NUMERIC,
    sleep_quality_score NUMERIC(3, 1),  -- 0-10
    
    -- Heart Rate metrics
    resting_hr_bpm NUMERIC(5, 1),
    min_hr_bpm NUMERIC(5, 1),
    max_hr_bpm NUMERIC(5, 1),
    avg_hr_bpm NUMERIC(5, 1),
    
    -- HRV metrics
    avg_hrv_ms NUMERIC,
    min_hrv_ms NUMERIC,
    hrv_z_score NUMERIC(5, 2),  -- deviation from baseline
    
    -- Activity metrics
    active_minutes INT,
    steps INT,
    active_energy_cal NUMERIC,
    basal_energy_cal NUMERIC,
    
    -- Mood/Stress (if available)
    stress_score NUMERIC(3, 1),  -- 0-10
    mood_note TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id, date)
);

CREATE INDEX idx_daily_summary_user_date ON daily_summary(user_id, date DESC);

-- HR Baselines: Hourly and day-of-week heart rate baseline (for anomaly detection)
CREATE TABLE IF NOT EXISTS hr_baselines (
    baseline_id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    hour_of_day INT CHECK(hour_of_day >= 0 AND hour_of_day < 24),
    day_of_week INT CHECK(day_of_week >= 0 AND day_of_week < 7),  -- 0=Mon, 6=Sun
    
    baseline_hr NUMERIC(5, 1),  -- 7-day rolling average
    baseline_std NUMERIC(5, 1),
    sample_count INT,
    
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id, hour_of_day, day_of_week)
);

-- HRV Baselines: Rolling HRV statistics per user + time window
CREATE TABLE IF NOT EXISTS hrv_baselines (
    baseline_id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    period_start_date DATE,
    period_end_date DATE,  -- typically 30 days
    
    baseline_hrv_30day_avg NUMERIC,
    baseline_hrv_std NUMERIC,
    z_score_threshold NUMERIC(5, 2),  -- alert if |z| > this
    
    anomaly_flag BOOLEAN DEFAULT FALSE,
    
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id, period_start_date)
);

-- Activity Patterns: Time-of-day + day-of-week motion patterns
CREATE TABLE IF NOT EXISTS activity_patterns (
    pattern_id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    day_of_week INT CHECK(day_of_week >= 0 AND day_of_week < 7),
    hour_of_day INT CHECK(hour_of_day >= 0 AND hour_of_day < 24),
    
    motion_type TEXT,  -- sedentary, walking, running, cycling, etc.
    location_cluster_id BIGINT REFERENCES location_clusters(cluster_id),
    
    frequency_count INT,  -- how often observed
    avg_hr_during NUMERIC(5, 1),
    
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id, day_of_week, hour_of_day, motion_type)
);

-- ============================================================================
-- SUGGESTION & FEEDBACK TABLES (for ML feedback loop)
-- ============================================================================

-- Suggestions: System-generated personalized suggestions
CREATE TABLE IF NOT EXISTS suggestions (
    suggestion_id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    suggestion_type TEXT NOT NULL,  -- morning_brief, break_rec, gym_pred, fatigue, habit_reinforce, etc.
    
    context_json JSONB,  -- variables used to generate suggestion (HR, weather, calendar, etc.)
    generated_text TEXT,
    
    confidence_score NUMERIC(3, 2),  -- 0.0-1.0
    
    ts_generated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ts_shown_to_user TIMESTAMP WITH TIME ZONE,
    
    expires_at TIMESTAMP WITH TIME ZONE,  -- suggestion TTL
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_suggestions_user_type ON suggestions(user_id, suggestion_type, ts_generated DESC);

-- Feedback: User response to suggestions
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id BIGSERIAL PRIMARY KEY,
    suggestion_id BIGINT NOT NULL REFERENCES suggestions(suggestion_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    action TEXT NOT NULL,  -- dismissed, accepted, snoozed, actioned
    user_reaction TEXT,    -- helpful, unhelpful, neutral
    
    reaction_time_sec INT,  -- time to interact
    
    ts_feedback TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    notes TEXT
);

CREATE INDEX idx_feedback_suggestion ON feedback(suggestion_id);

-- ============================================================================
-- HABIT TRACKING (for Use Case #5: Habit Reinforcement)
-- ============================================================================

CREATE TABLE IF NOT EXISTS habit_tracking (
    habit_id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    habit_name TEXT NOT NULL,  -- e.g., "3 workouts per week", "8h sleep on Sunday"
    habit_type TEXT,  -- workout_frequency, sleep_target, meditation, steps, etc.
    
    target_value INT,  -- e.g., 3 for "3 workouts/week"
    target_period TEXT,  -- week, month, day
    
    rolling_week_count INT,
    rolling_month_count INT,
    
    streak_days INT DEFAULT 0,
    longest_streak_days INT DEFAULT 0,
    
    last_reinforcement_ts TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- CORRELATION & ML TABLES (for Advanced Use Cases)
-- ============================================================================

-- Correlation Signals: Meeting density vs health metrics
CREATE TABLE IF NOT EXISTS correlation_signals (
    signal_id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    date DATE NOT NULL,
    
    meeting_count INT,
    meeting_minutes INT,
    
    avg_hr_during_meetings NUMERIC(5, 1),
    avg_hrv_during_meetings NUMERIC,
    stress_score_delta NUMERIC(5, 2),  -- vs baseline
    
    correlation_strength NUMERIC(3, 2),  -- -1 to 1
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id, date)
);

-- Device Integration Map: Normalize data from multiple wearables
CREATE TABLE IF NOT EXISTS device_sources (
    source_id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    device_name TEXT,  -- Apple Watch, Oura Ring, Garmin, etc.
    device_type TEXT,  -- wearable, phone, web
    
    source_label TEXT,  -- internal reference (Apple Watch, iPhone, etc.)
    
    data_normalized_from TIMESTAMP WITH TIME ZONE,  -- start date of normalization
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, device_name, source_label)
);

-- ============================================================================
-- Grants (if needed, adjust for your database user)
-- ============================================================================
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO pulse;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO pulse;

-- ============================================================================
-- Done!
-- ============================================================================
-- To load data: python migrate_to_schema.py
-- To test queries: See notebook cells #9 for example queries
