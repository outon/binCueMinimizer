# coding=cp1252
#
# binCueMinimizer.py
#
# Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0) 2019 granmacco <@granmacco>
# https://github.com/granmacco
#
# Script inspired by @krcroft's reddit post on June 25th, 2019
# https://www.reddit.com/r/RetroPie/comments/c50djy/chd_compression_summary_for_psx/
# https://github.com/krcroft
# Thank you very much, without you, this automation wouldn't have existed!
#
# Also, special thanks to @Kactius and @Jcarliman for finding @krcroft's post,
# putting me on the right track and inspiring some of the features of this script.
# https://github.com/kactius
# https://github.com/jcarliman
# Thank you very much for sharing your knowledge and for striving for excellence!
#
# This code is licensed under Creative Commons BY-NC-SA 4.0
# You may redistribute it and/or modify it under the terms of the
# Creative Commons BY-NC-SA 4.0 License, as published by the Creative
# Commons on their website http://creativecommons.org/licenses/by-nc-sa/4.0/
#

import logging
import os
import os.path as osp
import platform
import re
import subprocess
import sys
from ntpath import basename
from pathlib import Path
from shutil import copy, rmtree
from subprocess import call

version = "1.01"
logging.basicConfig(
    level=logging.DEBUG,
    filename="binCueMinimizer.log",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
)


class os_fs_helper:
    def __init__(self):
        self.original_dir = Path().absolute()
        self.working_dir = None

    def create_working_dir(self, path=None):
        """
        Crea un directorio de trabajo

        Parameters
        ----------
        :param path : str
            La raíz en la que crear el directorio de trabajo

        Returns
        -------
        :return str
            Ruta absoluta del directorio de trabajo

        """

        if path is None:
            path = self.get_original_dir()
        name_candidate = "temp"
        if os.path.isdir(os.path.join(path, name_candidate)):
            logging.debug(name_candidate + " existe. Busquemos otro")
            count = 1
            while os.path.isdir(os.path.join(path, name_candidate + str(count))):
                logging.debug(name_candidate + str(count) + " existe. Busquemos otro")
                count += 1
            name_candidate = name_candidate + str(count)
        logging.debug("Creando directorio " + name_candidate)
        os.mkdir(os.path.join(path, name_candidate))

        self.working_dir = os.path.join(path, name_candidate)

        return self.working_dir

    def get_original_dir(self):
        """
        Devuelve el directorio original de ejecución

        Returns
        -------
        :return str
            Ruta absoluta del directorio original de ejecución

        """

        return self.original_dir

    def get_working_dir(self):
        """
        Devuelve el directorio de trabajo

        Returns
        -------
        :return str
            Ruta absoluta del directorio de trabajo

        """

        return self.working_dir

    def delete_working_dir(self):
        """
        Borra el directorio de trabajo

        """
        if self.working_dir is not None:
            rmtree(self.working_dir)

    def enter_working_dir(self):
        os.chdir(self.working_dir)

    def exit_working_dir(self):
        os.chdir(self.original_dir)

    def copy_files_to_original_dir(self, files):
        """
        Copia desde ficheros al directorio original de ejecucion

        """
        self.copy_files_to_dir(files, self.get_original_dir())

    def copy_files_to_dir(self, files, directory):
        """
        Copia desde ficheros al directorio indicado

        """

        for file in files:
            copy(os.path.join(self.get_working_dir(), file), directory)

    def delete_files(self, files):
        if files:
            for file in files:
                os.remove(file)


class Validate:
    pass


class BinCueMinimizer:
    def __init__(self):
        self.base_cue_to_chd_command = "chdman createcd -i %INPUT -o %OUTPUT"
        self.base_bin_to_wav_command = (
            "ffmpeg -y -hide_banner -nostats -loglevel panic -f s16le "
            "-ar 44.1k -ac 2 -i %INPUT -f wav -flags +bitexact "
            "-acodec pcm_s16le -ar 44100 -ac 2 %OUTPUT"
        )
        self.base_lossywav_command = "lossywav %INPUT -o ./ -q X -D 2 -U 4 -m -a 4 -s h -A --feedback 3 --limit 15848"
        self.base_lossywav_compliance_command = (
            "ffmpeg -y -hide_banner -nostats -loglevel panic "
            "-i %INPUT -f wav -flags +bitexact -acodec pcm_s16le "
            "-ar 44100 -ac 2 %OUTPUT"
        )
        self.base_wav_to_bin_command = (
            "ffmpeg -y -hide_banner -nostats -loglevel panic "
            "-ac 2 -i %INPUT -f s16le -ar 44.1k -ac 2 %OUTPUT"
        )
        self.filename_chdman = "chdman"
        self.filename_lossywav = "lossyWAV"
        self.filename_ffmpeg = "ffmpeg"
        self.regex_file_line = re.compile(
            r"(?:FILE|file|File) (?:\'|\")(.*)(?:\'|\").*"
        )
        self.regex_track_line = re.compile(
            r"(?:TRACK|track|Track) \d* (AUDIO|audio|Audio)"
        )

    def run(self, command, replacements=None):
        """
        Lanza el comando suministrado, realizando sustituciones si se especifican.
    
        Parameters
        ----------
        :param command : list
            El comando con sus diferentes argumentos
        :param replacements : dictionary { str : str }
            Los reemplazos a realizar, siendo la clave el valor a sustituir y el valor la sustitución en sí
        
        Returns
        -------
        :return str
            La salida de consola
    
        """

        if replacements:
            for replacement in replacements:
                command = [
                    replacements[replacement] if x == replacement else x
                    for x in command
                ]
        logging.debug("Running " + " ".join(command))
        print("\n$ " + " ".join(command) + "\n")
        if not type(command) == list:
            raise TypeError(
                sys._getframe().f_code.co_name
                + " must be called with an %r" % "list of str"
            )
        result = call(command, stdout=subprocess.PIPE, shell=False)
        return result

    def get_dependencies(self):
        is_windows = platform.system() == "Windows"
        dependencies = [
            self.filename_chdman,
            self.filename_ffmpeg,
            self.filename_lossywav,
        ]
        dependencies = [
            filename + ".exe" if is_windows else filename for filename in dependencies
        ]
        return dependencies

    def check_dependencies(self, original_dir):
        for dependency in self.get_dependencies():
            logging.debug("Comprobando " + dependency)
            if not os.path.isfile(os.path.join(original_dir, dependency)):
                msg = (
                        'Error: No se encuentra el fichero necesario "'
                        + dependency
                        + '". Asegurese de tenerlo en la misma ruta que el script'
                )
                logging.debug(msg)
                raise SystemExit(msg)

    def copy_game_to_dir(self, cues, working_dir, original_dir, new_path=None):
        """
        Copia un juego al directorio especificado, por defecto, el de trabajo
    
        Para ello, se debe suministrar la ruta del .cue. Entonces se parseará,
        y sólo se moverán aquellos ficheros especificados en el cue.
    
        Parameters
        ----------
        :param cues : list [str]
            Las rutas al fichero cue
        :param original_dir:
        :param working_dir:
        :param new_path : str
            La ruta a la que copiar el juego. Por defecto, el directorio de trabajo
    
        Returns
        -------
        :return list [str]
            Las nuevas rutas de los ficheros cue

        """

        if type(cues) is not list:
            cues = [cues]
        if new_path is None:
            new_path = working_dir
        files_to_process = []
        path = original_dir
        for cue in cues:
            logging.debug("Copiando juego " + cue + " al directorio " + working_dir)
            bins = self.from_cue_to_bin(cue)
            for fbin in bins:
                copy(os.path.join(path, fbin["bin"]), new_path)
            copy(os.path.join(path, cue), new_path)
            files_to_process.append(os.path.join(new_path, basename(cue)))
        return files_to_process

    def write_cues_text(self, cues, filename):
        text_file = open(filename, "w")
        for cue in cues:
            text_file.write(cue)
            text_file.write("\n")
        text_file.close()

    def get_cues(self, original_dir, path=None):
        """
        Dada una ruta, obtiene los ficheros.cue
    
        Parameters
        ----------
        :param original_dir
            El directorio original.
        :param path : str
            El directorio a comprobar. Por defecto, el directorio de ejecución

        Returns
        -------
        :return list [str]
            Las rutas de los ficheros cue
    
        """

        if path is None:
            path = original_dir
        files_to_process = []
        for filename in os.listdir(path):
            filepath = os.path.join(path, filename)
            if osp.isdir(filepath):
                continue
            elif os.path.splitext(filename)[1].lower() == ".cue":
                logging.debug("Encontrado cue: " + filepath)
                files_to_process.append(filepath)
        return files_to_process

    def get_cues_without_audio_tracks(self, cues):
        """
        Elimina los juegos con pistas de audio de la lista de cues suministrada
    
        Parameters
        ----------
        :param cues : list [str]
            Los cues a filtrar
    
        Returns
        -------
        :return list [str]
            Aquellos cues que pertenecen al listado original, y que no contienen pistas de audio
    
        """

        cues_with_audio_tracks = self.get_cues_with_audio_tracks(cues)
        return [cue for cue in cues if cue not in cues_with_audio_tracks]

    def get_cues_with_audio_tracks(self, cues):
        """
        Elimina los juegos sin pistas de audio de la lista de cues suministrada
    
        Parameters
        ----------
        :param cues : list [str]
            Los cues a filtrar
    
        Returns
        -------
        :return list [str]
            Aquellos cues que pertenecen al listado original, y que contienen pistas de audio
    
        """

        if type(cues) is not list:
            cues = [cues]
        files_to_process = []
        for cue in cues:
            cue_contents = []
            has_audio_tracks = False
            with open(cue, "r") as file:
                cue_contents = file.read().split("\n")
            for line in cue_contents:
                regex_result = self.regex_track_line.search(line)
                if regex_result:
                    has_audio_tracks |= regex_result.group(1).lower() == "audio"
            if has_audio_tracks:
                logging.debug("Cue con audio tracks: " + cue)
                files_to_process.append(cue)
            else:
                logging.debug("Cue SIN audio tracks: " + cue)
        return files_to_process

    def from_cue_to_bin(self, cues):
        """
        Parsea un fichero cue y devuelve los bin asociados
        
        No tiene sentido llamarlo con un cue que no tenga pistas de audio
    
        Parameters
        ----------
        :param cues : list [str]
            Los cues a procesar
    
        Returns
        -------
        :return list [str]
            Las rutas absolutas de los ficheros bin
    
        """

        if type(cues) is not list:
            cues = [cues]
        files_to_process = []
        for cue in cues:
            result = {}
            # cue_contents = []
            with open(cue, "r") as file:
                cue_contents = file.read().split("\n")
            for line in cue_contents:
                if "bin" in result:
                    regex_result = self.regex_track_line.search(line)
                    if regex_result:
                        result["audio"] = regex_result.group(1).lower() == "audio"
                        logging.debug("Encontrado audio para bin " + result["bin"])
                    else:
                        result["audio"] = False
                        logging.debug(
                            "Encontrado pista de datos para bin " + result["bin"]
                        )
                    files_to_process.append(result)
                    result = {}
                else:
                    regex_result = self.regex_track_line.search(line)
                    if regex_result:
                        logging.debug(
                            "!!! OJO !!! El juego "
                            + cue
                            + " tiene pistas de audio sin fichero asociado !!! OJO !!!"
                        )
                regex_result = self.regex_file_line.search(line)
                if regex_result:
                    result["bin"] = regex_result.group(1)
                    logging.debug("Encontrado bin: " + result["bin"])
        return files_to_process

    def filter_audio_tracks(self, bins):
        """
        Filtra las pistas de datos de la lista suministrada
    
        Parameters
        ----------
        :param bins : list [str]
            Los bins a procesar
    
        Returns
        -------
        :return list [str]
            Las rutas absolutas de los ficheros bin de pistas de audio
    
        """

        if type(bins) is not list:
            bins = [bins]
        files_to_process = []
        # Uso fbin en lugar de bin porque bin es una palabra reservada
        for fbin in bins:
            if fbin["audio"]:
                files_to_process.append(fbin)
                logging.debug("Tiene pistas de audio, se queda: " + fbin["bin"])
            else:
                logging.debug("NO tiene pistas de audio, FUERA: " + fbin["bin"])
        return files_to_process

    def from_bin_to_wav(self, bins):
        """
        Convierte los ficheros bin PCM suministrados en wav
    
        Parameters
        ----------
        :param bins : list [str]
            Los bin a procesar
    
        Returns
        -------
        :return list [str]
            Las rutas absolutas de los ficheros wav
    
        """

        if type(bins) is not list:
            bins = [bins]
        files_to_process = []
        # Uso fbin en lugar de bin porque bin es una palabra reservada
        for fbin in bins:
            if fbin["audio"]:  # Solo por si acaso
                source = fbin["bin"]
                target = source[:-3] + "WAV"
                self.run(
                    self.base_bin_to_wav_command.split(),
                    {"%INPUT": source, "%OUTPUT": target},
                )
                files_to_process.append(target)
        return files_to_process

    def apply_lossywav_to_wav(self, wavs):
        """
        Aplica el lossywav a una lista de wavs
    
        Parameters
        ----------
        :param wavs : list [str]
            Los wavs a procesar
    
        Returns
        -------
        :return list [str]
            Las rutas absolutas de los ficheros wavs procesados con lossywav
    
        """

        if type(wavs) is not list:
            wavs = [wavs]
        files_to_process = []
        for wav in wavs:
            source = wav
            target = source[:-3] + "lossy.WAV"
            self.run(self.base_lossywav_command.split(), {"%INPUT": source})
            files_to_process.append(target)
        return files_to_process

    def fix_lossywav_compliance(self, wavs):
        """
        Elimina impurezas de los ficheros de lossywav suministrados en la lista
    
        Parameters
        ----------
        :param wavs : list [str]
            Los wavs a procesar
    
        Returns
        -------
        :return list [str]
            Las rutas absolutas de los ficheros wavs procesados
    
        """

        if type(wavs) is not list:
            wavs = [wavs]
        files_to_process = []
        for wav in wavs:
            source = wav
            target = source[:-9] + "WAV"
            self.run(
                self.base_lossywav_compliance_command.split(),
                {"%INPUT": source, "%OUTPUT": target},
            )
            files_to_process.append(target)
        return files_to_process

    def from_wav_to_bin(self, wavs):
        """
        Convierte los ficheros wav suministrados a bin PCM
    
        Parameters
        ----------
        :param wavs : list [str]
            Los wavs a procesar
    
        Returns
        -------
        :return list [str]
            Las rutas absolutas de los ficheros bin
    
        """

        if type(wavs) is not list:
            wavs = [wavs]
        files_to_process = []
        for wav in wavs:
            source = wav
            target = source[:-3] + "BIN"
            self.run(
                self.base_wav_to_bin_command.split(),
                {"%INPUT": source, "%OUTPUT": target},
            )
            files_to_process.append(target)
        return files_to_process

    def from_cue_to_chd(self, cues, suffix=None):
        """
        Convierte los cues suministrados en CHD
    
        Parameters
        ----------
        :param cues : list [str]
            Los cues a procesar
        :param suffix:

        Returns
        -------
        :return list [str]
            Las rutas absolutas de los CHD resultantes
    
        """

        if type(cues) is not list:
            cues = [cues]
        files_to_process = []
        for cue in cues:
            source = cue
            target = source[:-3]
            if suffix:
                target += suffix + "."
            target += "CHD"
            print("Processing " + source + "...")
            self.run(
                self.base_cue_to_chd_command.split(),
                {"%INPUT": source, "%OUTPUT": target},
            )
            files_to_process.append(target)
        return files_to_process


def main():
    fs = os_fs_helper()
    minimizer = BinCueMinimizer()
    minimizer.check_dependencies(fs.original_dir)
    cues = minimizer.get_cues(fs.original_dir)
    cues_with_audio_tracks = minimizer.get_cues_with_audio_tracks(cues)
    cues_without_audio_tracks = minimizer.get_cues_without_audio_tracks(cues)
    minimizer.write_cues_text(cues_with_audio_tracks, "games.with.audio.txt")
    minimizer.write_cues_text(cues_without_audio_tracks, "games.without.audio.txt")

    # Como el procesado de los juegos con pistas de audio ocupa más, se hará primero

    # Los juegos con pistas han de preprocesarse.
    if cues_with_audio_tracks:
        working_dir = fs.create_working_dir()
        fs.copy_files_to_dir(minimizer.get_dependencies(), working_dir)

        try:
            # Primero, hago la version lossy, para ocupar disco duro el mínimo tiempo posible
            temp_cues_with_audio_tracks = minimizer.copy_game_to_dir(
                cues_with_audio_tracks, working_dir, fs.original_dir
            )
            fs.enter_working_dir()
            try:
                bins = minimizer.from_cue_to_bin(temp_cues_with_audio_tracks)
                audio_bins = minimizer.filter_audio_tracks(bins)
                wavs = minimizer.from_bin_to_wav(audio_bins)
                lossy_wavs = minimizer.apply_lossywav_to_wav(wavs)
                compliant_lossy_wavs = minimizer.fix_lossywav_compliance(lossy_wavs)
                fs.delete_files(lossy_wavs)
                lossywav_bins = minimizer.from_wav_to_bin(compliant_lossy_wavs)
                fs.delete_files(compliant_lossy_wavs)
                lossywav_chds = minimizer.from_cue_to_chd(
                    temp_cues_with_audio_tracks, suffix="lossy"
                )
                fs.delete_files(lossywav_bins)
                fs.copy_files_to_original_dir(lossywav_chds)
            finally:
                fs.exit_working_dir()
        finally:
            fs.delete_working_dir()
        # Ahora, hago el CHD version no lossy, por si acaso para comparar
        minimizer.from_cue_to_chd(cues_with_audio_tracks)

    # Los juegos sin pistas se pueden procesar del tiron
    if cues_without_audio_tracks:
        minimizer.from_cue_to_chd(cues_without_audio_tracks)


if __name__ == "__main__":
    main()
