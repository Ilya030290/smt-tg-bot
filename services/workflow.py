from telegram.ext import ContextTypes


def reset_workflow_state(context: ContextTypes.DEFAULT_TYPE):
    
    keys = [
        'waiting_for_bom',
        'waiting_for_pnp',
        'bom_file',
        'waiting_for_bom_after_generation',
        'waiting_for_validation_answer',
        'pnp_for_validation',
        'waiting_for_excel_to_pnp',
        'waiting_for_pnp_to_excel',
        'waiting_for_first_file',
        'waiting_for_second_file',
        'first_file_path',
        'first_file_name',
        'waiting_for_gen_file1',
        'waiting_for_gen_file2',
        'waiting_for_gen_params',
        'gen_file1',
        'gen_file1_name',
        'gen_data',
        'gen_param_step',
        'df',
        'last_compare_result',
    ]

    for key in keys:
        context.user_data.pop(key, None)
