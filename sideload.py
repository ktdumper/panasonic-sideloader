import os
import sys
import shutil
import struct
import configparser
from io import StringIO
import re
import argparse
import logging

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def rm_f(path):
    try:
        os.remove(path)
    except OSError:
        pass

def patch_jam(jam, jar_len, package_url):
    config = configparser.ConfigParser()
    config.optionxform = str

    try:
        config.read_string("[jam]\r\n" + jam.decode("cp932"))
    except UnicodeDecodeError as e:
        print("WARN: can't patch jam properly due to non-CP932 encoding or other UnicodeDecodeError.")
        print(f"({e})")
        try:
            config.read_string("[jam]\r\n" + jam.decode("cp932", errors="ignore"))
        except configparser.ParsingError:
            return jam


    config["jam"]["PackageURL"] = package_url
    config["jam"]["LastModified"] = "Fri, 01 Jan 2010 00:00:00"
    config["jam"]["AppSize"] = str(jar_len)

    if "AppName" not in config["jam"]:
        config["jam"]["AppName"] = "No Name"

    if "AppClass" not in config["jam"]:
        logging.warning("No AppClass in the jam")

    default_values = {
        "AccessUserInfo": "yes",
        "GetSysInfo": "yes",
        "UseTelephone": "call",
        "UseDTV": "launch",
        "UseStorage": "ext",
        "TrustedAPID": "00000000000",
        "GetUtn": "userid,terminalid",
        "AppTrace": "on",
        "LaunchApp": "yes"
    }
    for key, value in default_values.items():
        config["jam"][key] = value

    sp_size = sum(int(s) for s in config["jam"].get("SPsize", "0").split(","))
    app_type = config["jam"].get("AppType")
    
    if app_type in ["FullApp", "MiniApp", "FullApp,MiniApp", "MiniApp,FullApp"]:
        config["jam"]["UseNetwork"] = "yes"
        
        if (jar_len + sp_size > 10 * 1024 * 1024):
            logging.warning("The total size of the jar and sp exceeds 10,240 KB.")
    elif app_type is None:
        config["jam"]["UseNetwork"] = "http"
        config["jam"]["MyConcierge"] = "yes"
        
        if (jar_len + sp_size > 1 * 1024 * 1024):
            logging.warning("The total size of the jar and sp exceeds 1,024 KB.")
    else:
        logging.warning(f"Invalid AppType: {app_type}")

    for option in ["TargetDevice", "MessageCode", "ProfileVer", "ConfigurationVer", "KvmVer"]:
        config["jam"].pop(option, None)

    config_string = StringIO()
    config.write(config_string)

    return config_string.getvalue()[6:].replace("\r\n", "\n").replace("\n", "\r\n").replace("\r\n\r\n", "\r\n").encode("cp932")

def make_sdf(package_url):
    config = configparser.ConfigParser()
    config.optionxform = str
    config["sdf"] = {
        "PackageURL": package_url,
        "CheckCnt": "000",
        "CheckInt": "000",
        "SuspendedCnt": "000",
        "Lmd": "20010606115743",
        "SkipConfirm": "launch",
        "GetLocationInfo": "yes",
        "AllowedHost": "any",
        "UseOpenGL": "yes",
        "UseBluetooth": "yes",
        "UseMailer": "yes",
        "GetPrivateInfo": "yes",
        "UseTcpPeerConnection": "yes",
        "UseUdpPeerConnection ": "yes",
        "UseATF": "yes",
        "UseVoiceInput": "yes",
        "UseDynamicClassLoader": "yes",
        "SetPhoneTheme": "yes",
        "SetLaunchTime": "yes",
        "RequestMyMenu": "yes",
        "RequestPayPerView": "yes",
        "AllowedLauncherApp": "any",
        "AllowedTcpHost": "any:15000",
        "AllowedUdpHost": "any:15000",
        "LaunchBySMS": "yes",
        "LaunchByDTV": "yes",
        "AppID": "000000000",
        "Sts": "0"
    }

    config_string = StringIO()
    config.write(config_string)
    
    sdf = config_string.getvalue()[6:].replace("\r\n", "\n").replace("\n", "\r\n").replace("\r\n\r\n", "\r\n").encode("cp932")
    sdfsize = len(sdf)
    
    sdf_template = struct.pack("<I 4s Q I I", 0, b"\xB7\xA1\x06\x67", 0, sdfsize, 0)

    return bytearray(sdf_template + sdf)

def process_input_directory(input_dir):
    jar_path = sp_path = jam_path = sdf_path = None

    for fname in os.listdir(input_dir):
        lower_fname = fname.lower()
        if lower_fname.endswith(".jar"):
            jar_path = fname
        elif lower_fname.endswith(".sp"):
            sp_path = fname
        elif lower_fname.endswith(".jam"):
            jam_path = fname
        elif lower_fname.endswith(".sdf"):
            sdf_path = fname

    if jar_path is None:
        raise FileNotFoundError(f"Can't find JAR file in: {input_dir}")
    if jam_path is None:
        raise FileNotFoundError(f"Can't find JAM file in: {input_dir}")

    return jar_path, sp_path, jam_path, sdf_path

def get_package_url(jam_content):
    package_url = re.search(r"PackageURL\s*=\s*([^\r\n]+)", jam_content.decode(encoding="cp932", errors="ignore"))
    if package_url:
        return package_url[1]
    logging.warning("No PackageURL in the jam")
    return "http://i-mode.localhost.ne.jp/sample.jar"

def generate_download_urls(package_url):
    if package_url.startswith("http"):
        jam_download_url = package_url.replace(".jar", ".jam").encode("cp932")
        jar_download_url = package_url.encode("cp932")
    elif m := re.search(r'.+?([^\r\n\/:*?"><|=]+\.jar)', package_url):
        jam_download_url = f'http://i-mode.localhost.ne.jp/{m[1].replace(".jar", ".jam")}'.encode("cp932")
        jar_download_url = f'http://i-mode.localhost.ne.jp/{m[1]}'.encode("cp932")
    else:
        jam_download_url = b"http://i-mode.localhost.ne.jp/sample.jam"
        jar_download_url = b"http://i-mode.localhost.ne.jp/sample.jar"
    return jam_download_url, jar_download_url

def get_next_available_number(install_dir):
    existing_dirs = [d for d in os.listdir(install_dir) if os.path.isdir(os.path.join(install_dir, d)) and d.isdigit()]
    if not existing_dirs:
        return 0
    return max(map(int, existing_dirs)) + 1

def process_folder(input_folder, install_dir):
    try:
        jar_path, sp_path, jam_path, sdf_path = process_input_directory(input_folder)

        with open(os.path.join(input_folder, jam_path), "rb") as inf:
            jam = inf.read()

        package_url = get_package_url(jam)
        jam_download_url, jar_download_url = generate_download_urls(package_url)

        adf_template = struct.pack("<I 2052s 4120s 148s 21496s 265s 2315s",
            1, jam_download_url, jar_download_url, b"\x71\x01", b"\x01", b"\xFF\xFF\xFF\xFF", b"\x01")
        
        jar_size = os.path.getsize(os.path.join(input_folder, jar_path))
        patched_jam = patch_jam(jam, jar_size, package_url)

        adf = bytearray(adf_template + patched_jam)
        adf[0x1820:0x1824] = struct.pack("<I", len(patched_jam))
        
        sdf = make_sdf(package_url)

        next_number = get_next_available_number(install_dir)
        output_path = os.path.join(install_dir, str(next_number))
        os.makedirs(output_path, exist_ok=True)

        with open(os.path.join(output_path, "adf"), "wb") as outf:
            outf.write(adf)

        if sp_path:
            with open(os.path.join(input_folder, sp_path), "rb") as inf:
                sp = inf.read()
            with open(os.path.join(output_path, "sp"), "wb") as outf:
                outf.write(sp[0x40:])

        shutil.copyfile(os.path.join(input_folder, jar_path), os.path.join(output_path, "jar"))

        if sdf_path:
            shutil.copyfile(os.path.join(input_folder, sdf_path), os.path.join(output_path, "sdf"))
        else:
            with open(os.path.join(output_path, "sdf"), "wb") as outf:
                outf.write(sdf)

        logging.info(f"Successfully Processed {input_folder} => {output_path}")

    except Exception as e:
        logging.error(f"An error occurred while processing {input_folder}: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="PA-Sideloader")
    parser.add_argument("input_dir", help="Input directory containing folders with JAR, JAM, and optionally SP and SDF files")
    parser.add_argument("install_dir", help="Install directory for patched files")
    args = parser.parse_args()

    setup_logging()

    if not os.path.isdir(args.input_dir):
        logging.error(f"Input directory does not exist: {args.input_dir}")
        sys.exit(1)

    if not os.path.exists(args.install_dir):
        os.makedirs(args.install_dir)

    folders_processed = 0
    items = os.listdir(args.input_dir)
    if any(item.lower().endswith('.jar') for item in items):
        process_folder(args.input_dir, args.install_dir)
        folders_processed = 1
    else:
        for item in items:
            item_path = os.path.join(args.input_dir, item)
            if os.path.isdir(item_path):
                process_folder(item_path, args.install_dir)
                folders_processed += 1
            else:
                logging.warning(f"Skipping non-directory item: {item}")

    logging.info(f"Processed {folders_processed} Application{'s' if folders_processed != 1 else ''}")

    for filename in ["Entry", "JavaAdl", "JavaSys", "PushSms"]:
        rm_f(os.path.join(args.install_dir, filename))

if __name__ == "__main__":
    main()
