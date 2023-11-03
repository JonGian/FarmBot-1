from database_interface import Database
from diffusers import DiffusionPipeline
import uuid, os, torch
import webcolors

class AI:
    # hardcoded positive prompt (things you want)
    POS_PROMPT = "artistic artwork, interesting shapes, abstract art, fluid art, (((masterpiece)))"
    # hardcoded negative prompt (things you don't want)
    NEG_PROMPT = "photo of plant"

    def generate_art(self, user_prompt: str, entry_ids: list, data_types: list, db: Database, img_seed: str):
        img_name = str(uuid.uuid4()) + ".jpg"
        img_path = "./ai_images" + os.sep + img_name

        # credits: https://github.com/huggingface/diffusers/tree/main/examples/community#stable-diffusion-xl-long-weighted-prompt-pipeline
        pipe = DiffusionPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0",
            torch_dtype=torch.float16,
            use_safetensors=True,
            variant="fp16",
            custom_pipeline="lpw_stable_diffusion_xl",
        )

        entries_prompt = []
        for entry_data in entry_ids:
            prompt = ""
            (
                entry_id,
                species_id,
                date_time,
                r,
                g,
                b,
                leaf_area,
                weather_id,
                leaf_count,
                leaf_circle,
                leaf_solid,
                leaf_ratio,
                species,
                weather_cond,
                temperature,
                x,
                y,
            ) = entry_data

            if "datetime" in data_types:
                prompt += f"date and time {date_time}, "
            if "species" in data_types:
                prompt += f"plant species {species}, "
            if "rgb" in data_types:
                col = (r, g, b)
                if r < 210 and g < 210 and b < 210:
                    col = boost_contrast((r, g, b), 2)
                colour = self.estimate_colour_text(col)
                prompt += f"colour {colour}, "
            if "leafarea" in data_types:
                prompt += f"area {leaf_area} cm squared, "
            if "weathercondition" in data_types:
                prompt += f"weather condition {weather_cond}, "
            if "temperature" in data_types:
                prompt += f"temperature {temperature} celsius, "
            if "leafcount" in data_types:
                prompt += f"(leaves: {leaf_count}), "
            if "leafcircle" in data_types:
                prompt += f"(circularity: {round(leaf_circle*100, 2)}%), "
            if "leafsolid" in data_types:
                prompt += f"(solidarity: {round(leaf_solid*100, 2)}%), "
            if "leafratio" in data_types:
                prompt += f"(aspect ratio: {round(leaf_ratio, 2)}%), "

            entries_prompt.append(prompt)

        prompt_parts = user_prompt.split(":")
        pos_prompt = prompt_parts[0]
        neg_prompt = prompt_parts[1]

        final_prompt = f"{self.POS_PROMPT}, {pos_prompt}, {', '.join(entries_prompt)}"

        final_neg_prompt = (
            f"{self.NEG_PROMPT}, {neg_prompt}"
        )

        print(f"Final prompt is {final_prompt}")
        print(f"Final negative prompt is {final_neg_prompt}")
        pipe.to("cuda")  # if cuda is available
        original_seed = torch.seed()
        generator = torch.Generator(device='cuda')
        print("original_seed : ", original_seed)

        if img_seed != "":
            # Set the seed to the value from img_seed
            new_seed = int(img_seed)
            torch.manual_seed(new_seed)
            generator = generator.manual_seed(new_seed)
            print("Manual seed: ", new_seed)
            # Now, capture the updated seed
            updated_seed = torch.seed()
            print("Updated seed: ", updated_seed)
            image = pipe(prompt=final_prompt, negative_prompt=final_neg_prompt, generator=generator).images[0]
        else:
            print("img_seed is empty")
            image = pipe(prompt=final_prompt, negative_prompt=final_neg_prompt).images[0]

        torch.cuda.empty_cache()

        image.save(img_path)

        return (img_path, final_prompt, original_seed)
    
    def estimate_colour_text(self, colour):
        try:
            return webcolors.rgb_to_name(colour) # return if theres exact colour
        except ValueError:
            return close_colour(colour) # guess colour

# stable diffusion doesn't understand rgb values, so this will return the closest colour word
# credits: https://stackoverflow.com/questions/9694165/convert-rgb-color-to-english-color-name-like-green-with-python
def close_colour(colour):
    min_colours = {}
    for key, name in webcolors.CSS3_HEX_TO_NAMES.items():
        r_c, g_c, b_c = webcolors.hex_to_rgb(key)
        rd = (r_c - colour[0]) ** 2
        gd = (g_c - colour[1]) ** 2
        bd = (b_c - colour[2]) ** 2
        min_colours[(rd + gd + bd)] = name
    return min_colours[min(min_colours.keys())]

# some colours lack contrast and cant guess a good colour, boosting contrast may help
def boost_contrast(colour, factor):
    r, g, b = colour
    r = max(0, min(255, r + (r - 128) * factor))
    g = max(0, min(255, g + (g - 128) * factor))
    b = max(0, min(255, b + (b - 128) * factor))
    return (int(r), int(g), int(b))