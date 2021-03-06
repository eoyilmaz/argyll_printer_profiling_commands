#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""This is the advanced GUI version of the Windows Command Line script
that does the ICC Profile creation.

Workflow:

from icc_generator import ICCGenerator
ig = ICCGenerator()

# Set Printer Details
ig.printer_brand
ig.printer_model

# Set Paper Details
ig.paper_brand
ig.paper_model
ig.paper_finish
ig.paper_size

# Set Ink Details
ig.ink_brand

# Profiling workflow

ig.generate_target()
ig.generate_tif_files()
ig.read_charts()
ig.generate_profile()
ig.check_profile(True)
# Optional
ig.read_charts(resume=True, read_mode=0) # use mode=1 for patch-by-patch
ig.install_profile()
"""
import os
import logging
from PySide2 import QtCore, QtGui, QtWidgets


logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)


__version__ = "0.3.1"
HERE = os.path.abspath(os.path.dirname(__file__))


class ICCGenerator(object):
    """Generates ICC profiles by using ArgyllCMS.

    This is a generic utility that works in all the operating systems.

    Windows Workflow Notes:

    - Use Dry Creek Photo Profile Target Printer (best option) or Adobe Color Print Utility (buggy, and scales images
      while printing).

    Linux Workflow notes:

    - Gimp + GutenPrint seems to be a very good option (set Color Correction to Uncorrected and Image Type to
      Photograph)

    - Use /usr/share/color/icc/ or ~/.local/share/icc to install the profiles

    If the ``use_high_density_mode`` is set to True the system uses the i1pro patch pattern which is much denser than
    the one for ColorMunki.

    If the ``use_high_density_mode`` is set to anything other than True, then the system will use two A4 pages or one A3
    page use:

    420 patches for A4 (in 2 A4 pages)
    460 patches for A3

    by setting the device to ``i1pro`` and the margins to 2 mm it is possible to print 672 (28x24) 7x8.75 mm patches for
    A4 and 1392 (58x24) 7x8.75 mm patches for A3 on a single page.

    what I want to achieve here is to use the minimum amount of paper for
    profiling and still have an excellent result

    Generated temp files are located under these folders:

        For Windows:

            $APPDATA/ICCGenerator/%{printer_brand}_%{printer_model}/%{profile_date}

        For Linux:

            ~/.cache/IccGenerator/%{printer_brand}_%{printer_model}/%{profile_date}

    folders.

    The final ICC profiles will be placed under these folders:

        For Windows:

            %WINDIR%/System32/spool/drivers/color/

        For Linux:

            ~/.local/share/icc/

    """
    A3 = "A3"
    A4 = "A4"
    NORMAL_DENSITY = 'normal_density'
    HIGH_DENSITY = 'high_density'

    __data__ = {
        'paper_size':
            {
                A3: {
                    'patch_count': {
                        NORMAL_DENSITY: 445,
                        HIGH_DENSITY: 1392,
                    }
                },
                A4: {
                    'patch_count': {
                        NORMAL_DENSITY: 210,
                        HIGH_DENSITY: 672,
                    }
                }
            }
    }

    def __init__(self, printer_brand="Canon", printer_model="iX6850", paper_brand="Kodak", paper_model="UPPP",
                 paper_finish="Glossy", paper_size=A4, ink_brand="CanonInk", use_high_density_mode=True,
                 number_of_pages=1, copyright_info="", precondition_profile_path="", output_commands=False,
                 gray_patch_count=16):

        self.output_commands = output_commands

        self._printer_brand = None
        self.printer_brand = printer_brand

        self._printer_model = None
        self.printer_model = printer_model

        self._paper_brand = None
        self.paper_brand = paper_brand

        self._paper_model = None
        self.paper_model = paper_model

        self._paper_finish = None
        self.paper_finish = paper_finish

        self._paper_size = None
        self.paper_size = paper_size

        self._ink_brand = None
        self.ink_brand = ink_brand

        self._use_high_density_mode = None
        self.use_high_density_mode = use_high_density_mode

        self._number_of_pages = None
        self.number_of_pages = number_of_pages

        self._gray_patch_count = None
        self.gray_patch_count = gray_patch_count

        self._copyright_info = None
        self.copyright_info = copyright_info

        self._precondition_profile_path = None
        self.precondition_profile_path = precondition_profile_path

        import datetime
        now = datetime.datetime.now()
        date_str = now.strftime("%Y%m%d")
        time_str = now.strftime("%H%M")

        self.profile_date = date_str
        self.profile_time = time_str

        # Profile Path template
        self._profile_path_template = \
            "~/.cache/ICCGenerator/{printer_brand}_" \
            "{printer_model}/{profile_date}"

        # Profile name template
        self.profile_name_template = \
            "{printer_brand}_{printer_model}_{paper_brand}_" \
            "{paper_model}_{paper_finish}_{paper_size}_{ink_brand}_" \
            "{profile_date}_{profile_time}"
        self._profile_name = ""

        self.tif_files = []

        # The output path is defined by the Operating system
        self.output_path = "~/.local/share/icc/"
        if os.name == 'nt':
            self.output_path = '%WINDIR%/System32/spool/drivers/color/'

    def save_settings(self, path=None):
        """saves the settings to the given path

        :param str path: The settings file path. If skipped the profile path will be used along with the profile name to
          generate a proper profile path.
        """
        if not path:
            path = os.path.join(self.profile_path, "%s.json" % self.profile_name)

        if not isinstance(path, str):
            raise TypeError("Please specify a valid path")

        data = {
            'ink_brand': self.ink_brand,
            'paper_brand': self.paper_brand,
            'paper_finish': self.paper_finish,
            'paper_model': self.paper_model,
            'paper_size': self.paper_size,
            'printer_brand': self.printer_brand,
            'printer_model': self.printer_model,
            'profile_date': self.profile_date,
            'profile_time': self.profile_time
        }

        # create the folder
        norm_path = os.path.expandvars(os.path.expanduser(path))
        os.makedirs(os.path.dirname(norm_path), exist_ok=True)

        import json
        with open(norm_path, 'w+') as f:
            json.dump(data, f)

    def load_settings(self, path):
        """loads the settings from the given path
        """
        if not path or not isinstance(path, str):
            raise TypeError("Please specify a valid path")

        norm_path = os.path.expandvars(os.path.expanduser(path))
        if not os.path.exists(norm_path):
            raise RuntimeError("File does not exist!: %s" % path)

        import json
        with open(norm_path, 'r') as f:
            data = json.load(f)

        self.ink_brand = data['ink_brand']
        self.paper_brand = data['paper_brand']
        self.paper_finish = data['paper_finish']
        self.paper_model = data['paper_model']
        self.paper_size = data['paper_size']
        self.printer_brand = data['printer_brand']
        self.printer_model = data['printer_model']
        self.profile_date = data['profile_date']
        self.profile_time = data['profile_time']

    @property
    def printer_brand(self):
        return self._printer_brand

    @printer_brand.setter
    def printer_brand(self, printer_brand):
        """getter for the printer_brand attribute
        """
        if not printer_brand or not isinstance(printer_brand, str):
            raise TypeError(
                "%s.printer_brand should be a str, not %s" % (
                    self.__class__.__name__, printer_brand.__class__.__name__
                )
            )
        self._printer_brand = printer_brand

    @property
    def printer_model(self):
        return self._printer_model

    @printer_model.setter
    def printer_model(self, printer_model):
        """getter for the printer_model attribute
        """
        if not printer_model or not isinstance(printer_model, str):
            raise TypeError(
                "%s.printer_model should be a str, not %s" % (
                    self.__class__.__name__, printer_model.__class__.__name__
                )
            )
        self._printer_model = printer_model

    @property
    def paper_brand(self):
        return self._paper_brand

    @paper_brand.setter
    def paper_brand(self, paper_brand):
        """getter for the paper_brand attribute
        """
        if not paper_brand or not isinstance(paper_brand, str):
            raise TypeError(
                "%s.paper_brand should be a str, not %s" % (
                    self.__class__.__name__, paper_brand.__class__.__name__
                )
            )
        self._paper_brand = paper_brand

    @property
    def paper_model(self):
        return self._paper_model

    @paper_model.setter
    def paper_model(self, paper_model):
        """getter for the paper_model attribute
        """
        if not paper_model or not isinstance(paper_model, str):
            raise TypeError(
                "%s.paper_model should be a str, not %s" % (
                    self.__class__.__name__, paper_model.__class__.__name__
                )
            )
        self._paper_model = paper_model

    @property
    def paper_finish(self):
        return self._paper_finish

    @paper_finish.setter
    def paper_finish(self, paper_finish):
        """getter for the paper_finish attribute
        """
        if not paper_finish or not isinstance(paper_finish, str):
            raise TypeError(
                "%s.paper_finish should be a str, not %s" % (
                    self.__class__.__name__, paper_finish.__class__.__name__
                )
            )
        self._paper_finish = paper_finish

    @property
    def paper_size(self):
        return self._paper_size

    @paper_size.setter
    def paper_size(self, paper_size):
        """getter for the paper_size attribute
        """
        if not paper_size or not isinstance(paper_size, str):
            raise TypeError(
                "%s.paper_size should be a str, not %s" % (
                    self.__class__.__name__, paper_size.__class__.__name__
                )
            )

        if paper_size not in self.__data__['paper_size']:
            raise ValueError(
                "%s.paper_size should be one of %s, not %s" % (
                    self.__class__.__name__,
                    list(self.__data__['paper_size'].keys()),
                    paper_size
                )
            )

        self._paper_size = paper_size

    @property
    def ink_brand(self):
        return self._ink_brand

    @ink_brand.setter
    def ink_brand(self, ink_brand):
        """getter for the ink_brand attribute
        """
        if not ink_brand or not isinstance(ink_brand, str):
            raise TypeError(
                "%s.ink_brand should be a str, not %s" % (
                    self.__class__.__name__, ink_brand.__class__.__name__
                )
            )
        self._ink_brand = ink_brand

    @property
    def use_high_density_mode(self):
        return self._use_high_density_mode

    @use_high_density_mode.setter
    def use_high_density_mode(self, use_high_density_mode):
        """getter for the use_high_density_mode attribute
        """
        if not isinstance(use_high_density_mode, bool):
            raise TypeError(
                "%s.use_high_density_mode should be a bool (True or False), not %s" % (
                    self.__class__.__name__, use_high_density_mode.__class__.__name__
                )
            )
        self._use_high_density_mode = use_high_density_mode

    @property
    def number_of_pages(self):
        return self._number_of_pages

    @number_of_pages.setter
    def number_of_pages(self, number_of_pages):
        """getter for the number_of_pages attribute
        """
        if not number_of_pages or not isinstance(number_of_pages, int):
            raise TypeError(
                "%s.number_of_pages should be a int, not %s" % (
                    self.__class__.__name__, number_of_pages.__class__.__name__
                )
            )
        self._number_of_pages = number_of_pages

    @property
    def copyright_info(self):
        return self._copyright_info

    @copyright_info.setter
    def copyright_info(self, copyright_info):
        """getter for the copyright_info attribute
        """
        if not isinstance(copyright_info, str):
            raise TypeError(
                "%s.copyright_info should be a str, not %s" % (
                    self.__class__.__name__, copyright_info.__class__.__name__
                )
            )
        self._copyright_info = copyright_info

    @property
    def precondition_profile_path(self):
        return self._precondition_profile_path

    @precondition_profile_path.setter
    def precondition_profile_path(self, precondition_profile_path):
        """getter for the precondition_profile_path attribute
        """
        if not isinstance(precondition_profile_path, str):
            raise TypeError(
                "%s.precondition_profile_path should be a str, not %s" % (
                    self.__class__.__name__, precondition_profile_path.__class__.__name__
                )
            )
        self._precondition_profile_path = precondition_profile_path

    @property
    def profile_path(self):
        """getter for the profile_path attribute
        """
        # update the output path according to the OS
        return self._profile_path_template.format(
            printer_brand=self.printer_brand,
            printer_model=self.printer_model,
            paper_brand=self.paper_brand,
            paper_model=self.paper_model,
            paper_finish=self.paper_finish,
            paper_size=self.paper_size,
            ink_brand=self.ink_brand,
            profile_date=self.profile_date,
            profile_time=self.profile_time
        )

    @property
    def profile_absolute_path(self):
        """returns the absolute path of profile_path variable
        """
        return os.path.expandvars(
            os.path.expanduser(
                self.profile_path
            )
        )

    @property
    def profile_absolute_full_path(self):
        """returns the absolute path of profile_path variable
        """
        return os.path.join(self.profile_absolute_path, self.profile_name)

    def render_profile_name(self):
        return self.profile_name_template.format(
            printer_brand=self.printer_brand,
            printer_model=self.printer_model,
            paper_brand=self.paper_brand,
            paper_model=self.paper_model,
            paper_finish=self.paper_finish,
            paper_size=self.paper_size,
            ink_brand=self.ink_brand,
            profile_date=self.profile_date,
            profile_time=self.profile_time
        )

    @property
    def profile_name(self):
        """getter for the profile_name attribute
        """
        if not self._profile_name:
            self.profile_name = self.render_profile_name()
        return self._profile_name

    @profile_name.setter
    def profile_name(self, profile_name):
        """setter for profile_name
        :param str profile_name:
        :return:
        """
        self._profile_name = profile_name

    @property
    def per_page_patch_count(self):
        """getter for the per_page_patch_count property
        """
        # Per Page Patch Count is Defined by the Paper Size and
        # the High Resolution mode
        resolution_str = self.HIGH_DENSITY if self.use_high_density_mode else self.NORMAL_DENSITY
        return self.__data__['paper_size'][self.paper_size]['patch_count'][resolution_str]

    @property
    def patch_count(self):
        """getter for the patch_count attribute
        """
        return self.per_page_patch_count * self.number_of_pages

    @property
    def gray_patch_count(self):
        """getter for the gray_patch_count attribute
        """
        return self._gray_patch_count

    @gray_patch_count.setter
    def gray_patch_count(self, gray_patch_count):
        """setter for the gray_patch_count property

        :param int gray_patch_count:
        :return:
        """
        if not gray_patch_count or not isinstance(gray_patch_count, int):
            raise TypeError(
                "%s.gray_patch_count should be an int, not %s" % (
                    self.__class__.__name__, gray_patch_count.__class__.__name__
                )
            )

        self._gray_patch_count = gray_patch_count

    @classmethod
    def run_external_process(cls, command, shell=False):
        """Runs an external process and yields the output

        :param command: The command to run
        :param bool shell: A bool value for executing the command in shell or not.
        """
        import subprocess
        if not shell:
            process = subprocess.Popen(
                command, stderr=subprocess.PIPE
            )
            # loop until process finishes and capture stderr output
            stderr_buffer = []
            while True:
                stderr = process.stderr.readline()

                if stderr == b'' and process.poll() is not None:
                    break

                if stderr != b'':
                    stderr = stderr.decode('utf-8').strip()
                    stderr_buffer.append(stderr)
                    yield stderr

            # flatten the buffer
            stderr_buffer = '\n'.join(stderr_buffer)
            return_code = process.returncode

            if return_code:
                # there is an error
                raise RuntimeError(stderr_buffer)
        else:
            command = " ".join(command)
            os.system(command)

    def generate_target(self):
        """generates the required ti1 file
        """
        os.makedirs(self.profile_absolute_path, exist_ok=True)

        # ************************
        # targen command
        command = [
            "targen", "-v", "-d", "2", "-G",
            "-g", "%s" % self.gray_patch_count,
            "-f", "%s" % self.patch_count
        ]
        if self.precondition_profile_path:
            command += ["-c", self.precondition_profile_path]
        command += [self.profile_absolute_full_path]

        # first call the targen command
        # yield from self.run_external_process(command)
        if self.output_commands:
            print("command: %s" % " ".join(command))
        for output in self.run_external_process(command):
            print(output)

    def generate_tif(self):
        """generates the required Tiff file or files depending on the page
        count
        """
        os.makedirs(self.profile_absolute_path, exist_ok=True)

        # ************************
        # printtarg command
        command = ["printtarg", "-v"]
        if self.use_high_density_mode:
            command += ["-ii1", "-a 0.875"]  # Use an i1 Pro
        else:
            command += ["-iCM", "-h", "-P"]  # Use a ColorMunki

        command += [
            "-R1", "-T300", "-M2", "-L",
            "-p", "420x297" if self.paper_size == "A3" else self.paper_size,
            self.profile_absolute_full_path
        ]

        self.update_tif_files()

        # first call the targen command
        # print("generate_tif_files command: %s" % ' '.join(command))
        # yield from self.run_external_process(command)
        if self.output_commands:
            print("command: %s" % " ".join(command))
        for output in self.run_external_process(command):
            print(output)

    def update_tif_files(self):
        """updates the tiff file paths
        """
        # update tif files
        self.tif_files = []
        if self.number_of_pages == 1:
            self.tif_files.append(
                os.path.expanduser(
                    os.path.join(
                        self.profile_path,
                        "%s.tif" % self.profile_name
                    )
                )
            )
        else:
            for i in range(self.number_of_pages):
                self.tif_files.append(
                    os.path.expanduser(
                        os.path.join(
                            self.profile_path,
                            "%s_%02i.tif" % (self.profile_name, i + 1)
                        )
                    )
                )

    def print_charts(self):
        """runs the proper application with the charts already open

        For Windows, it will first try to run Dry Creek Photo Print Utility if
        exist and if not then it will try to run Adobe Color Printer Utility,
        and if it doesn't exists either it will raise a proper RuntimeError
        stating that the user should install Dry Creek Photo Print Utility or
        ACPU.

        For Linux, it will first check if GIMP and GutenPrint is installed,
        if not will raise a RuntimeError to inform the user, if they exists
        properly it will open GIMP with the Tiff file.
        """
        if os.name == 'nt':  # Windows
            # call Dry Creek Photo Print Utility first
            # if it fails then try to call ACPU
            # if this fails too, raise a RuntimeError
            # TODO: implement and test this on Windows
            pass
        elif os.name == 'posix':  # Linux
            # call Gimp with the TIFF Files
            command = ['/usr/bin/gimp'] + self.tif_files
        if self.output_commands:
            print("command: %s" % " ".join(command))
        for output in self.run_external_process(command):
            print(output)

    def read_charts(self, resume=False, read_mode=0):
        """Reads the printed chart using the device

        :param bool resume: If a .ti3 files already exists and ``resume`` is
          set to True. The process will start from where it left before.
          Default value is False

        :param int read_mode: There are two possible modes:

            0: Strip Mode
            1: Patch-By-Patch

          Use ``read_mode=1`` (Patch-By-Patch) with ``resume=True`` to fix
          erroneously read patches.

        :return:
        """
        os.makedirs(self.profile_absolute_path, exist_ok=True)

        # ************************
        # chartread command
        command = ["chartread", "-v", "-H", "-T 0.4"]
        if read_mode == 1:
            command += ["-p", "-P"]

        if resume:
            command += ["-r"]

        command += [self.profile_absolute_full_path]

        # first call the targen command

        # os.system(" ".join(command))
        # yield from self.run_external_process(command, shell=True)
        if self.output_commands:
            print("command: %s" % " ".join(command))
        for output in self.run_external_process(command, shell=True):
            print(output)

    def generate_profile(self):
        """generates the profile
        """
        os.makedirs(self.profile_absolute_path, exist_ok=True)

        # ************************
        # colprof command
        command = [
            "colprof", "-v", "-qh", "-r0.5", "-S",
            os.path.join(HERE, "../AdobeRGB.icc"),
            "-cmt", "-dpp", "-Zr", "-Zm",
            "-D%s" % self.profile_name
        ]

        if self.copyright_info:
            command.append("-C%s" % self.copyright_info)

        command += [self.profile_absolute_full_path]

        # call the command
        # yield from self.run_external_process(command)
        if self.output_commands:
            print("command: %s" % " ".join(command))
        for output in self.run_external_process(command):
            print(output)

    def check_profile(self, sort_by_dE=False):
        """Checks the profile quality
        """
        os.makedirs(self.profile_absolute_path, exist_ok=True)

        # ************************
        # prof_check
        command = [
            "profcheck", "-k", "-v2",
        ]
        if sort_by_dE:
            command.append('-s')

        command.append("%s.ti3" % self.profile_absolute_full_path)

        if os.name == 'nt':
            # windows uses *.icm file extension
            command.append("%s.icm" % self.profile_absolute_full_path)
        else:
            # OSX and Linux uses *.icc file extension
            command.append("%s.icc" % self.profile_absolute_full_path)

        # call the command
        # yield from self.run_external_process(command)
        if self.output_commands:
            print("command: %s" % " ".join(command))
        for output in self.run_external_process(command):
            print(output)

    def install_profile(self):
        """Installs the generated profile to appropriate folders depending on the current OS

        For Windows:

            %WINDIR%/System32/spool/drivers/color/

        For Linux:

            ~/.local/share/icc/

        """
        import shutil
        # check if the profile is not generated yet
        icc_profile_absolute_full_path = "%s.icc" % self.profile_absolute_full_path
        if not os.path.exists(icc_profile_absolute_full_path):
            raise RuntimeError("ICC file doesn't exist, please generate it first!")

        profile_install_path = os.path.expandvars(
            os.path.expanduser(
                os.path.join(
                    self.output_path,
                    '%s.icc' % self.profile_name
                )
            )
        )

        shutil.copy2(
            icc_profile_absolute_full_path,
            profile_install_path
        )

    @classmethod
    def color_correct_image(cls, printer_profile_path=None, input_image_path=None, output_image_path=None, image_profile="AdobeRGB", intent="r"):
        """Apply color correction to the given image. Accepts TIFF or JPEG files.

        cctiff
        ~/.local/share/icc/Canon_iX6850_Generic_Plain_Matte_A4_CanonInk_20210207_1402.icc
        ~/Documents/development/ICCGenerator/sRGB.icc
        Primary_Colors_3.jpeg
        Primary_Colors_3_corrected2.jpeg

        cctiff
          ~/Documents/development/ICCGenerator/sRGB-elle-V2-srgbtrc.icc
          ~/.local/share/icc/Canon_iX6850_Generic_Plain_Matte_A4_CanonInk_20210207_1402.icc
          Primary_Colors_3.jpeg
          Primary_Colors_3_corrected.jpeg

        :param str printer_profile_path: The path of the ICC/ICM file of the printer profile.
        :param str image_profile: Can be either "sRGB" or "AdobeRGB", default is "AdobeRGB".
        :param str input_image_path: The input JPG/TIFF image path.
        :param str output_image_path: The output TIFF image path.
        :param str intent: Rendering intent, one of the following:

          p = perceptual, r = relative colorimetric (default)
          s = saturation, a = absolute colorimetric

        :return:
        """
        # ---------------------
        # Printer Profile Path
        if printer_profile_path is None or not isinstance(printer_profile_path, str):
            raise TypeError("Please specify a proper printer_profile_path!")

        if not os.path.exists(os.path.expandvars(os.path.expanduser(printer_profile_path))):
            raise ValueError("printer_profile_path doesn't exists: %s" % printer_profile_path)

        printer_profile_extension = os.path.splitext(printer_profile_path)[-1]
        if printer_profile_extension.lower() not in ['.icc', '.icm']:
            raise ValueError("printer_profile_path should be a valid ICC/ICM file: %s" % printer_profile_path)

        # ---------------------
        # Input Image Path
        if not isinstance(input_image_path, str):
            raise TypeError("Please specify a proper input_image_path!")

        if not os.path.exists(os.path.expandvars(os.path.expanduser(input_image_path))):
            raise ValueError("input_image_path doesn't exists: %s" % input_image_path)

        input_image_extension = os.path.splitext(input_image_path)[-1]
        if input_image_extension.lower() not in ['.jpg', '.tif', '.tiff']:
            raise ValueError("input_image_path should be a valid JPG/TIF file: %s" % input_image_path)

        if not output_image_path:
            # generate the output_image_path from input_image_path
            base_name = os.path.basename(input_image_path)
            dir_name = os.path.dirname(input_image_path)
            base_name_wo_ext, ext = os.path.splitext(input_image_path)
            i = 1
            while i < 100000:
                output_image_path = os.path.join(dir_name, "%s_corrected_%s%s" % (base_name_wo_ext, i, ext))
                if not os.path.exists(output_image_path):
                    break
                i += 1

        if os.path.splitext(output_image_path)[-1].lower() not in ['.jpg', '.tif', '.tiff']:
            raise ValueError("output_image_path should be a valid JPG/TIF file: %s" % output_image_path)

        # ---------------------
        # Intent
        if not intent:
            # use default
            intent = "r"

        if not isinstance(intent, str):
            raise TypeError("intent should be a string, not %s" % intent.__class__.__name__)

        if intent not in ["p", "r", "s", "a"]:
            raise ValueError("intent should be one of p, r, s, a, not %s" % intent)

        # ---------------------
        # Image Profile
        if image_profile is None:
            image_profile = "AdobeRGB"

        if not isinstance(image_profile, str):
            raise TypeError("image_profile should be one of sRGB or AdobeRGB, not %s" % image_profile)

        if not os.path.isfile(image_profile):
            if image_profile not in ["AdobeRGB", "sRGB"]:
                raise ValueError("image_profile should be one of sRGB or AdobeRGB, not %s" % image_profile)
            image_profile_path = os.path.normpath(os.path.join(HERE, "..", "%s.icc" % image_profile))
        else:
            image_profile_path = image_profile

        # ************************
        # cctiff
        command = [
            "cctiff",
            "-i", intent,
            "-p", image_profile_path,
            printer_profile_path,
            input_image_path,
            output_image_path,
        ]

        # call the command
        # yield from self.run_external_process(command)
        print("command: %s" % " ".join(command))
        for output in cls.run_external_process(command):
            print(output)


class UI(object):
    """The UI
    """
    pass


class MainWindow(QtWidgets.QMainWindow):
    """
    """

    __company_name__ = 'Erkan Ozgur Yilmaz'
    __app_name__ = 'ICC Generator'
    __version__ = __version__

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent=parent)
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("%s v%s" % (self.__app_name__, self.__version__))

        self.create_main_menu()
        self.create_toolbars()
        self.create_dock_widgets()

        self.read_settings()

    def write_settings(self):
        """stores the settings to persistent storage
        """
        self.settings.beginGroup("MainWindow")

        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("windowState", self.saveState())

        self.settings.endGroup()

    def read_settings(self):
        """read settings from persistent storage
        """
        self.settings.beginGroup('MainWindow')

        self.resize(self.settings.value('size', QtCore.QSize(800, 600)))
        self.move(self.settings.value('pos', QtCore.QPoint(100, 100)))
        self.restoreState(self.settings.value('windowState'))

        self.settings.endGroup()

    def reset_window_state(self):
        """reset window states
        """
        self.project_dock_widget.setVisible(True)

    def create_main_menu(self):
        """creates the main application menu
        """
        file_menu = self.menuBar().addMenu(self.tr(b"&File"))

        file_menu.addSeparator()

    def create_toolbars(self):
        """creates the toolbars
        """
        file_toolbar = self.addToolBar(self.tr(b"File"))
        file_toolbar.setObjectName('file_toolbar')
        create_project_action = file_toolbar.addAction('Create Project')

    def create_dock_widgets(self):
        """creates the dock widgets
        """
        pass
