// Discrete-clock safety only. Both resets assert together; releases may differ.
reg f_seen = 0;
reg f_previous_ref_reset, f_previous_dco_reset;
always @($global_clock) begin
    f_seen <= 1;
    f_previous_ref_reset <= REF_RESET_N;
    f_previous_dco_reset <= DCO_RESET_N;
    if (!f_seen) begin
        assume(!REF_RESET_N && !DCO_RESET_N);
    end else begin
        if (f_previous_ref_reset && !REF_RESET_N) assume(!DCO_RESET_N);
        if (f_previous_dco_reset && !DCO_RESET_N) assume(!REF_RESET_N);
        assert(!APPLIED || (REF_RESET_N && DCO_RESET_N && APPLIED_COMMAND == COMMAND));
    end
end

reg f_ref_valid;
reg f_ref_busy;
reg [WIDTH-1:0] f_previous_payload;
reg f_previous_request;
always @(posedge REFCLK or negedge REF_RESET_N) begin
    if (!REF_RESET_N) begin
        f_ref_valid <= 0;
        f_ref_busy <= 0;
        f_previous_payload <= 0;
        f_previous_request <= 0;
    end else begin
        if (f_ref_valid && f_ref_busy) begin
            assert(payload == f_previous_payload);
            assert(request == f_previous_request);
        end
        f_ref_valid <= 1;
        f_ref_busy <= acknowledge_sync != request;
        f_previous_payload <= payload;
        f_previous_request <= request;
    end
end

reg f_destination_valid;
reg f_capture_valid;
reg [WIDTH-1:0] f_captured_payload;
reg [COUNT_WIDTH:0] f_consumer_age;
reg f_previous_acknowledge;
always @(posedge DCOCLK or negedge DCO_RESET_N) begin
    if (!DCO_RESET_N) begin
        f_destination_valid <= 0;
        f_capture_valid <= 0;
        f_captured_payload <= 0;
        f_consumer_age <= 0;
        f_previous_acknowledge <= 0;
    end else begin
        if (f_destination_valid && f_capture_valid)
            assert(APPLIED_COMMAND == f_captured_payload);
        if (f_destination_valid && acknowledge != f_previous_acknowledge) begin
            assert(f_capture_valid);
            assert(f_consumer_age >= APPLY_CYCLES);
        end
        if (capture_pending) begin
            f_captured_payload <= payload;
            f_consumer_age <= 0;
            f_capture_valid <= 1;
        end else if (f_capture_valid && f_consumer_age < APPLY_CYCLES) begin
            f_consumer_age <= f_consumer_age + 1'b1;
        end
        f_destination_valid <= 1;
        f_previous_acknowledge <= acknowledge;
    end
end
