// Sampled REFCLK-domain controls only. No analog, CDC or physical timing claim.
// Verification-only insertion into the pinned, otherwise unchanged RTL module.
reg formal_past_valid = 0;
reg formal_ack_once = 0;
reg formal_seed_confirmed = 0;
wire formal_seed_ack = TUNING_APPLIED && LOADED_FINE == FINE_SEED;
wire formal_bad_program = STARTUP_COARSE > 47 || STARTUP_FINE < 8 ||
                          STARTUP_FINE > 247 || KI == 0;
always @(posedge REFCLK) begin
    formal_past_valid <= 1;
    // Independently count consecutive observations of the actual loaded seed.
    // A later LOAD visit must establish its own two-observation confirmation.
    if (!RESET_N || !REF_RESET_N) begin
        formal_ack_once <= 0;
        formal_seed_confirmed <= 0;
    end else if (state == LOAD) begin
        formal_seed_confirmed <= formal_seed_ack && formal_ack_once;
        formal_ack_once <= formal_seed_ack;
    end else begin
        formal_ack_once <= 0;
        if (state != READY && state != START && state != RUN)
            formal_seed_confirmed <= 0;
    end
    if (formal_past_valid) begin
        assert(state <= FAIL);
        if (state == SETTLE || state == LOAD || CONFIG_READY || RUN_FINE) begin
            assert(COARSE_CODE <= 47);
            assert(FINE_SEED >= 8 && FINE_SEED <= 247);
            assert(CONFIGURED_KI != 0);
        end
        if (CONFIG_READY || RUN_FINE)
            assert(formal_seed_confirmed);
        if (FAILED) begin
            assert(!OSC_RESET_N);
            assert(!CONFIG_READY && !RUN_FINE);
        end
        if (RESET_N && REF_RESET_N) begin
            if ($past(RESET_N && REF_RESET_N && FAILED))
                assert(FAILED);
            if ($past(RESET_N && REF_RESET_N && state != CAPTURE && changed))
                assert(FAILED);
            if ($past(RESET_N && REF_RESET_N && state == CAPTURE && formal_bad_program))
                assert(FAILED);
            if ($past(RESET_N && REF_RESET_N && state != CAPTURE))
                assert({COARSE_CODE, FINE_SEED, INCREASING, CONFIGURED_KI, CONFIGURED_KP}
                       == $past({COARSE_CODE, FINE_SEED, INCREASING, CONFIGURED_KI, CONFIGURED_KP}));
        end
    end
end
