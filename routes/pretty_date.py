from datetime import datetime
import platform

def pretty_date(dt, show_time=False):
    if not dt:
        return "No date"

    if isinstance(dt, str):
        try:
            if "T" in dt:
                dt = datetime.fromisoformat(dt)
                show_time = True
            else:
                dt = datetime.fromisoformat(dt)
        except ValueError:
            return dt  

    suffix = "th"
    if dt.day in [1, 21, 31]:
        suffix = "st"
    elif dt.day in [2, 22]:
        suffix = "nd"
    elif dt.day in [3, 23]:
        suffix = "rd"

    base = f"{dt.strftime('%B')} {dt.day}{suffix}"

    if show_time:
        hour_fmt = "%-I" if platform.system() != "Windows" else "%#I"
        time_str = dt.strftime(f"{hour_fmt}:%M %p")
        return f"{base} at {time_str}"

    return base
