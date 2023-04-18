import csv
import sys
from os import path

sys.path.append(path.dirname(path.dirname(__file__)))

from misc.compute_dependencies import compute_dependencies

list_of_contracts_2_3_clp = [
    "Gyro2CLPMath",
    "Gyro2CLPPool",
    "Gyro2CLPPoolErrors",
    "Gyro2CLPPoolFactory",
    "ExtensibleBaseWeightedPool",
    "Gyro3CLPMath",
    "Gyro3CLPPool",
    "Gyro3CLPPoolErrors",
    "Gyro3CLPPoolFactory",
]

list_of_contracts_eclp = [
    "GyroECLPMath",
    "GyroECLPPool",
    "GyroECLPPoolErrors",
]

list_of_contracts_top_level = [
    "CappedLiquidity",
    "ExtensibleWeightedPool2Tokens",
    "Freezable Proxy" "LocallyPausable",
]

list_of_libraries = [
    "Buffer",
    "GyroConfigKeys",
    "GyroFixedPoint",
    "GyroPoolMath",
    "QueryProcessor",
    "Samples",
    "SignedFixedPoint",
]


def main():
    with open("all_vault_dependencies.csv", "w", newline="") as csvfile:
        fieldnames = ["Gyro Contract", "Dependency Contract", "Path"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for contract in (
            list_of_contracts_2_3_clp
            + list_of_contracts_eclp
            + list_of_contracts_top_level
            + list_of_libraries
        ):
            dependencies = compute_dependencies(contract)
            sorted_dependencies = sorted(dependencies.items(), key=lambda v: v[1])
            for i in sorted_dependencies:
                writer.writerow(
                    {
                        "Gyro Contract": contract,
                        "Dependency Contract": i[0],
                        "Path": i[1],
                    }
                )


if __name__ == "__main__":
    main()
