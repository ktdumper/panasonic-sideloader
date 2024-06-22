import os
import sys
import shutil


def rm_f(path):
    try:
        os.remove(path)
    except OSError:
        pass


def main():
    input_dir = sys.argv[1]
    output_dir = sys.argv[2]

    jar_path = sp_path = jam_path = None

    for fname in os.listdir(input_dir):
        if fname.endswith(".jar"):
            jar_path = fname
        elif fname.endswith(".sp"):
            sp_path = fname
        elif fname.endswith(".jam"):
            jam_path = fname

    if jar_path is None:
        raise RuntimeError("can't find jar")
    elif sp_path is None:
        raise RuntimeError("can't find sp")
    elif jam_path is None:
        raise RuntimeError("can't find jam")

    with open(os.path.join(input_dir, sp_path), "rb") as inf:
        sp = inf.read()

    with open("adf_template", "rb") as inf:
        adf = bytearray(inf.read())

    with open(os.path.join(input_dir, jam_path), "rb") as inf:
        jam = inf.read()

    adf += jam
    adf[0x1820:0x1824] = len(jam).to_bytes(4, byteorder="little")

    target = None

    for x in range(512):
        if not os.path.exists(os.path.join(output_dir, str(x))):
            target = x
            break

    if target is None:
        raise RuntimeError("no target folder")

    output_path = os.path.join(output_dir, str(target))

    os.mkdir(output_path)
    with open(os.path.join(output_path, "adf"), "wb") as outf:
        outf.write(adf)
    with open(os.path.join(output_path, "sp"), "wb") as outf:
        outf.write(sp[0x40:])
    shutil.copyfile(os.path.join(input_dir, jar_path), os.path.join(output_path, "jar"))

    for filename in ["Entry", "JavaAdl", "JavaSys", "PushSms"]:
        rm_f(os.path.join(output_dir, filename))

    print("{} => {}".format(input_dir, output_path))


if __name__ == "__main__":
    main()
