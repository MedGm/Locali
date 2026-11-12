# Run E in 5 bits on the laptop: the answers only

Run E as a Q5_K_M file (`../../8_improve/quant`), all 164 HumanEvalFix problems, llama.cpp 987498f
with n-gram lookup, 4 threads (2026-11-12, `experiments/scripts/laptop/laptop_runE_q5.sh`).

**102 fixed** (4 bits: 95, `../laptop_3b_energy_runE`); 11 fixed only at 5 bits, 4 only at 4,
exact McNemar p = 0.12. Peak RAM 2.50 GB (4 bits: 2.23).

The time and energy of this run are not to be used: the energy counter was not readable (no
energy recorded), the file was read from an external drive and other work ran on the laptop. The
clean measurement of both sizes is `../laptop_3b_energy_runG`.

Code and text written with AI help (Claude).
