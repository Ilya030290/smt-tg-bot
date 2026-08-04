def calculate_offsets(board_width, board_height, x_count, y_count, pitch_x, pitch_y, rotated_blocks):
    offsets = []
    total = x_count * y_count

    def format_num(n):
        if isinstance(n, float) and n.is_integer():
            return str(int(n))
        return str(n)

    if total == 2 and len(rotated_blocks) == 1:
        for n in range(1, total + 1):
            if n in rotated_blocks:
                offsets.append(f"{format_num(board_width)};{format_num(board_height)};180")
            else:
                offsets.append("0;0;0")
        return offsets

    for n in range(1, total + 1):
        row = (n - 1) // x_count
        col = (n - 1) % x_count
        if n in rotated_blocks:
            x_off = board_width - ((x_count - 1 - col) * pitch_x)
            y_off = board_height - ((y_count - 1 - row) * pitch_y)
            r = 180
        else:
            x_off = col * pitch_x
            y_off = row * pitch_y
            r = 0
        offsets.append(f"{format_num(x_off)};{format_num(y_off)};{r}")
    return offsets
